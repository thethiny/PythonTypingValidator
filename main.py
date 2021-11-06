import typing
from typing import (
    _SpecialForm,
    Any,
    Dict,
    ForwardRef,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    Type,
    TypedDict,
    TypeVar,
    Union,
    _TypedDictMeta, # type: ignore
)

i = int
st = str
f = float
n = None
d = dict
l = list
s = set


class TestClass(TypedDict):
    item_str: str
    item_int: int
    item_float: float
    item_none: None
    item_dict: dict
    item_list: list
    item_set: set


def get_typing_args(typing) -> Tuple[Type[Any]]:
    if typing.__module__ == "typing":
        return tuple(arg for arg in typing.__args__ if arg not in typing.__parameters__)  # type: ignore
    return None,


_T = TypeVar("_T")


def typed_eval(type_: str, ret_type: Type[_T]) -> _T:
    x: _T = eval(type_)
    return x
    

def parse_type(
    typing_type: Union[str, type, Type[Any]], globals_dict={}
) -> Tuple[Type[Any]]:

    globals_dict = globals_dict or globals()

    if typing_type == type:
        return (type,)

    if typing_type is None:
        return (None,)

    if isinstance(typing_type, str):
        typing_type = typed_eval(typing_type, type)

    if isinstance(typing_type, _TypedDictMeta):
        if hasattr(typing_type, "__annotations__"):
            return (TypedDict,)
        else:
            return (dict,)  # No annotations means basically empty dict

    if isinstance(typing_type, type):  # Standard Types
        return (typing_type,)

    if typing_type.__module__ == "typing":

        if typing_type == Type:
            return (type,)

        if isinstance(typing_type, ForwardRef):
            if not globals_dict:
                raise Exception("ForwardRefs require a globals_dict")
            try:
                return parse_type(typing_type._evaluate(globals_dict, locals()), globals_dict)
            except NameError as e:
                raise Exception(
                    f"ForwardRef {typing_type} could not be resolved as {e}"
                ) from e

        if not hasattr(typing_type, "__origin__"):
            raise Exception(f"Unsupported typing type {typing_type}")

        if isinstance(typing_type, _SpecialForm):
            return typing_type,

        typing_type_origin = typing_type.__origin__  # type: ignore

        if isinstance(typing_type_origin, _SpecialForm):
            if typing_type_origin == Any:
                return Any,
            if typing_type_origin == Union: # Optional becomes Union[None, ...]
                return get_typing_args(typing_type)
            if typing_type_origin == Literal:
                return Literal,
            raise Exception(f"Unsupported typing type {typing_type}")


        return parse_type(typing_type_origin)

    # Custom Types

    return (typing_type,)

def get_subtypes(
    typing_type: Union[str, type, Type[Any]], type_: Type[Any], globals_dict={}
) -> List[Union[Tuple[Any], Tuple[Any, Any]]]:
    globals_dict = globals_dict or globals()
    # If typeddict, then go over annotations
    if None in (typing_type, type_):
        return [(None,)]
    if isinstance(typing_type, _TypedDictMeta):
        x = tuple(get_typing_args(v) for v in typing_type.__annotations__.values())

        return [
            (str,), (x,)
        ]

    name = getattr(typing_type, "_name", "")
    # If list, set, dict, then go over args if they are typing types else return Any
    if name in ("List", "Set"):
        args = get_typing_args(typing_type)
        if len(args) > 1:
            raise Exception(f"{typing_type} can only have 1 type")
        if len(args) == 0:
            return [(Any,)]
        return [parse_type(args[0], globals_dict)]
    if name == "Dict":
        args = get_typing_args(typing_type)
        if len(args) > 2:
            raise Exception(f"{typing_type} can only have 2 types")
        if len(args) == 0:
            return [(Any,), (Any,)]
        if len(args) == 1:
            raise Exception(f"{typing_type} needs to have 2 types")
        
        key, value = args # type: ignore
        return [parse_type(key, globals_dict), parse_type(value, globals_dict)]    
    if name == "Tuple":
        args = get_typing_args(typing_type)
        if len(args) == 0:
            return [(Any,)]
        return [parse_type(arg, globals_dict) for arg in args]
    if name == "Union":
        return [(None,)]
    if name == "Literal":
        args = get_typing_args(typing_type)
        if not args:
            raise Exception(f"{typing_type} needs to have at least 1 value")
        return [(None,)]

    if typing_type in (set, list, tuple):
        return [(Any,)]
    if typing_type == dict:
        return [(Any,), (Any,)]

    if isinstance(typing_type, ForwardRef):
        return get_subtypes(typing_type._evaluate(globals_dict, locals()), type_, globals_dict)


    return [(None,)] # Unknown

def istypeddict(type_: Any, typeddict: _TypedDictMeta, globals_dict = {}) -> bool:
    globals_dict = globals_dict or globals()
    if not isinstance(type_, dict):
        return False

    if not typeddict.__total__:
        return True

    for key in typeddict.__annotations__:
        if key not in type_: # Missing Key
            return False
    
    for key in type_:
        if key not in typeddict.__annotations__:
            return False # Extra Key
        if not isinstance(key, str):
            return False # Key is not a string

        type_guessed = parse_type(typeddict.__annotations__[key])
        type_values = get_subtypes(typeddict.__annotations__[key], type_guessed, globals_dict)

        if not validate_item(type_[key], type_guessed, type_values):
            return False # Invalid Value
    
    return True
        
    

def validate_item(
    item: Any, types: Tuple[Type[Any], ...], type_values, globals_dict={}
) -> bool:
    globals_dict = globals_dict or globals()
    try:
        if isinstance(item, types):
            return True
    except Exception:
        ...

    for type_ in types:
        if isinstance(type_, _TypedDictMeta):
            if isinstance(item, (dict, Dict)):
                if istypeddict(item, type_):
                    return True
            else:
                continue
        if type_ is None:
            if item is None:
                return True
            else: continue

        if type_ == Any:
            return True

        if type_ == Literal:
            if item in type_values:
                return True
            else: continue

        if type_ == Union: # Impossible
            if isinstance(item, type_values):
                return True
            else: continue

        if type_ in [Tuple, tuple]:
            if not isinstance(type_, tuple):
                continue
            if not type_values:
                return True
            if len(item) != len(type_values):
                continue
            for i in range(len(item)):
                all_success = True
                if not validate_item(item[i], type_values[i], globals_dict):
                    all_success = False
                    break
                return all_success

        if type_ in (List, Set, list, set):
            if not type_values:
                return True
            if not isinstance(item, type_):
                continue
            for i in item:
                all_success = True
                if not validate_item(i, type_values, globals_dict):
                    all_success = False
                    break
                return all_success

        if type_ in (Dict, dict):
            if not isinstance(item, dict):
                continue
            if not type_values:
                return True
            key_types, value_types = type_values
            all_success = True
            for key, value in type_.items(): # type: ignore
                if not validate_item(key, key_types, globals_dict):
                    all_success = False
                    break
                if not validate_item(value, value_types, globals_dict):
                    all_success = False
                    break
            return all_success




        if type(type_) == type and isinstance(item, type_):
            return True

    return False



if __name__ == "__main__":
    for type_ in (
        i,
        st,
        f,
        n,
        d,
        l,
        s,
        TestClass,
        "float",
        List,
        List[int],
        Tuple,
        Tuple[int, str, int, int],
        Union[str, int],
        Dict,
        Dict[str, int],
        ForwardRef("TestClass"),
        ForwardRef("Dict[str, int]"),
        ForwardRef("Union[str, int]"),
        Literal[1, 7, "hey", str]
    ):
        parsed_types = parse_type(type_, globals())
        parsed_sub_types = get_subtypes(type_, parsed_types, globals())
        if len(parsed_sub_types) == 2:
            # Dict or Tuple
            ...
        elif len(parsed_sub_types) == 1:
            ...
            # Any
        else:
            # Tuple
            ...
        joined_subs = ' | '.join([str(p) for p in parsed_sub_types])
        try:
            joined_subs = " | ".join(', '.join([getattr(t, "__name__", str(t))]) for tt in parsed_sub_types for t in tt)
        except Exception:
            ...
        try:
            joined_subs = " | ".join(', '.join([getattr(r, "__name__", str(r)) for r in t]) for tt in parsed_sub_types for t in tt)
        except Exception:
            ...
        try:
            joined_parses = ", ".join(getattr(t, "__name__", str(t)) for t in parsed_types)
        except Exception:
            joined_parses = str(parsed_types)

        print(
            "Type:",
            getattr(type_, "__name__", type_),
            "|",
            "Parsed:",
            joined_parses,
            "|",
            "SubTypes:",
            joined_subs,
            end=" | ",
        )

        validated_types = []

        int_ = validate_item(1, parsed_types, parsed_sub_types)
        if int_:
            validated_types.append("int")

        float_ = validate_item(1.0, parsed_types, parsed_sub_types)
        if float_:
            validated_types.append("float")

        str_ = validate_item("hey", parsed_types, parsed_sub_types)
        if str_:
            validated_types.append("str")
        
        dict_ = validate_item({"hey": 1}, parsed_types, parsed_sub_types)
        if dict_:
            validated_types.append("dict")

        list_ = validate_item([1, 2, 3], parsed_types, parsed_sub_types)
        if list_:
            validated_types.append("list")
        
        set_ = validate_item({1, 2, 3}, parsed_types, parsed_sub_types)
        if set_:
            validated_types.append("set")
        
        tuple_ = validate_item((1, 2, 3), parsed_types, parsed_sub_types)
        if tuple_:
            validated_types.append("tuple")
        
        none_ = validate_item(None, parsed_types, parsed_sub_types)
        if none_:
            validated_types.append("None")

        print("Validation:", " | ".join([str(v) for v in validated_types]) if validated_types else "Failed", end = "")

        print()
