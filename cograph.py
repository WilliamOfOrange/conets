import numpy as np
import matplotlib.pyplot as plt
from abc import ABC, abstractclassmethod
from dataclasses import dataclass, field
from uuid import uuid4, UUID
from typing import Dict, Tuple, List, Union


@dataclass
class PhysicalProperties:
    resistance_ohms: float
    capacitance_farads: float
    inductance_teslas: float
    temperature_delta_celsius: float


@dataclass
class ApparentEMFState:
    potential_volts: float
    current_probe_amps: float
        
        
class ComponentNode(ABC):
    
    def __init__(self):
        super().__init__()
    
    @abstractclassmethod
    def on_initialisation(self, ambient_temp_c: float) -> 'ComponentNode':
        raise NotImplementedError()
    
    @abstractclassmethod
    def on_line_connect(self, component_line_key: str, line_uuid: UUID, line_properties: PhysicalProperties):
        raise NotImplementedError()
    
    @abstractclassmethod
    def on_line_disconnect(self, component_line_key: str, line_id: UUID):
        raise NotImplementedError()
    
    @abstractclassmethod
    def on_tdelta(self, tick: int, edge_deltas: Dict[str, Tuple[ApparentEMFState, PhysicalProperties]]) -> Dict[str, Tuple[ApparentEMFState, PhysicalProperties]]:
        raise NotImplementedError()

    @abstractclassmethod
    def on_set_attribute(self, key: str, value: any) -> bool:
        return False 
    
    @property
    @abstractclassmethod
    def attribute_lookup(self) -> Dict[str, type]:
        return {}
        
    @property
    @abstractclassmethod
    def input_basis_table(self) -> Dict[str, PhysicalProperties]:
        """ 
        Physical properties calculated per SI basis units:
            1 volt @ 1 amp @ 25c ambient temperature
        Returns:
            PhysicalProperties: Properties of the component
        """
        raise NotImplementedError()
    

class LineEdge:
    uuid: UUID
    conductor: PhysicalProperties
    
    u_component_id: str
    u_component_pin: str
    v_component_id: str
    u_component_pin: str

    def __repr__(self) -> str:
        return f"{str(self.uuid)=} [{self.u_component_id}:{self.u_component_pin}] -> [{self.v_component_id}:{self.v_component_pin}]"
    
    def __init__(self, *args):
        self.conductor = args[0]
        self.u_component_id = args[1]
        self.u_component_pin = args[2]
        self.v_component_id = args[3]
        self.v_component_pin = args[4]
        self.uuid = uuid4()


class Resistor(ComponentNode):
    _basis: PhysicalProperties = None
    _state: dict = None
        
    def __init__(self, **kw):
        super().__init__()
        self._basis = PhysicalProperties(1000, 0., 0., 0.)
        self._state = {
            'temp_c': 25,
            'pins': {
                'p1': [self._basis, dict()],
                'p2': [self._basis, dict()]
            },
            'ticks': 0
        }

    def input_basis_table(self) -> Dict[str, PhysicalProperties]:
        return {
            "p1", self._basis,
            "p2", self._basis
        }
    
    def on_initialisation(self, ambient_temp_c: float) -> 'ComponentNode':
        self._state['temp_c'] = ambient_temp_c
        return self
        
    def on_line_connect(self, component_line_key: str, line_uuid: UUID, line_properties: PhysicalProperties):
        self._state['pins'][component_line_key][1][str(line_uuid)] = line_properties 
    
    def on_line_disconnect(self, component_line_key: str, line_id: UUID):
        self._state['pins'][component_line_key][1].pop(str(line_id))
    
    def on_tdelta(self, tick: int, edge_deltas: Dict[UUID, Tuple[ApparentEMFState, PhysicalProperties]]) -> PhysicalProperties:
        raise NotImplementedError()


    def on_set_attribute(self, key: str, value: any) -> bool:
        return False 
    
    @property
    def attribute_lookup(self) -> Dict[str, type]:
        return {}

class VoltageDC(ComponentNode):
    _basis: PhysicalProperties = None
    _attrib_type_map: dict = None
    _state: dict = None
    
    def __init__(self): 
        super().__init__()
        self._basis = PhysicalProperties(0., 0., 0., 0.)
        self._attributes = {
            'voltage_selector_state': float
        }
        self._state = {
            'temp_c': 25,
            'pins': {
                'pos': [self._basis, dict()],
                'neg': [self._basis, dict()]
            },
            'ticks': 0,
            'attributes': dict.fromkeys(self._attributes)
        }
            
    def on_initialisation(self, ambient_temp_c: float) -> 'ComponentNode':
        self._state['temp_c'] = ambient_temp_c
        return self
    
    def on_line_connect(self, component_line_key: str, line_uuid: UUID, line_properties: PhysicalProperties):
        self._state['pins'][component_line_key][1][str(line_uuid)] = line_properties
    
    
    def on_line_disconnect(self, component_line_key: str, line_id: UUID):
        self._state['pins'][component_line_key][1].pop(str(line_id))
    
    
    def on_tdelta(self, tick: int, edge_deltas: Dict[str, Tuple[ApparentEMFState, PhysicalProperties]]) -> Dict[str, Tuple[ApparentEMFState, PhysicalProperties]]:
        raise NotImplementedError()

    
    def on_set_attribute(self, key: str, value: any) -> bool:
        # no exceptions for now as attributes not critical to
        # running and evaluation
        if key not in self._attrib_type_map:
            return False
        elif not isinstance(value, self._attrib_type_map[key]): 
            return False
        self._state['attribute'][key] = value 
   
    @property
    def attribute_lookup(self) -> Dict[str, type]:
        return self._attrib_type_map
        
    @property
    def input_basis_table(self) -> Dict[str, PhysicalProperties]: 
        return {
            'pos': self._basis,
            'neg:': self._basis  
        }
        

class CircuitGraph:
    _labels: Dict[str, Union[ComponentNode, LineEdge]]
    _l_edges: List[LineEdge] = None
    _c_nodes: List[ComponentNode] = None
    
        
    def __init__(self):
        self._l_edges = list()
        self._c_nodes = list()
        self._labels = dict()
        
    def __repr__(self):
        repr: str = str('')
        repr += '\nComponents:\n\t' + '\n\t'.join([f'[{str(c)}]' for c in self._c_nodes])
        repr += '\nNode List:\n\t' + '\n\t'.join([f'[{str(e)}]' for e in self._l_edges])
        return repr
     
    def define(self, label: str, item: Union[ComponentNode, LineEdge]):
        if label in self._labels:
            raise KeyError('CircuitGraph.define(): Cannot define component')
        if isinstance(item, ComponentNode):
            self._c_nodes.append(item)
            self._labels[label] = self._c_nodes[-1]
        elif isinstance(item, LineEdge):
            self._l_edges.append(item)
            self._labels[label] = self._l_edges[-1]
        else: 
            raise TypeError(f"CircuitGraph.define(): Attempt to add unrecognised item type provided: {type(item).__name__}  with label {label}.")
        

    def link(self, 
            label: str, 
            component_u_label_pin: Tuple[str, str], 
            component_v_label_pin: Tuple[str, str], 
            line_properties: PhysicalProperties = PhysicalProperties(.1, 0., 0., 0.)):
        u_id, u_pin = component_u_label_pin
        v_id, v_pin = component_v_label_pin
        edge = LineEdge(line_properties, u_id, u_pin, v_id, v_pin)
        self._labels[u_id].on_line_connect(u_pin, edge.uuid, line_properties)
        self._labels[v_id].on_line_connect(v_pin, edge.uuid, line_properties)
        self.define(label, edge)
        return edge.uuid
    
    
