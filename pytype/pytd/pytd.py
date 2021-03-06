# -*- coding:utf-8; python-indent:2; indent-tabs-mode:nil -*-

# Copyright 2013 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Our way of using namedtuple is confusing pylint.
# pylint: disable=no-member

"""AST representation of a pytd file."""


import itertools
from pytype.pytd.parse import node


class TypeDeclUnit(node.Node('name', 'constants', 'type_params', 'classes',
                             'functions', 'aliases')):
  """Module node. Holds module contents (constants / classes / functions).

  Attributes:
    name: Name of this module, or None for the top-level module.
    constants: Iterable of module-level constants.
    type_params: Iterable of module-level type parameters.
    functions: Iterable of functions defined in this type decl unit.
    classes: Iterable of classes defined in this type decl unit.
    aliases: Iterable of aliases (or imports) for types in other modules.
  """
  __slots__ = ()

  def Lookup(self, name):
    """Convenience function: Look up a given name in the global namespace.

    Tries to find a constant, function or class by this name.

    Args:
      name: Name to look up.

    Returns:
      A Constant, Function or Class.

    Raises:
      KeyError: if this identifier doesn't exist.
    """
    # TODO(kramm): Put constants, functions, classes and aliases into a
    # combined dict.
    try:
      return self._name2item[name]
    except AttributeError:
      self._name2item = {}
      module_name, _, _ = name.rpartition('.')
      if module_name == self.name:
        # The names in this module are fully qualified
        prefix = self.name + '.'
      else:
        prefix = ''
      for x in self.type_params:
        # There are hard-coded type parameters in the code (e.g., T for
        # sequences), so the module prefix must be added here rather than
        # directly to the parameter names.
        self._name2item[prefix + x.name] = x
      for x in self.constants + self.functions + self.classes + self.aliases:
        if x.name in self._name2item:
          raise AttributeError(
              'Duplicate name %s found: %s and %s' % (
                  x.name, type(self._name2item[x.name]), type(x)))
        self._name2item[x.name] = x
      return self._name2item[name]

  # The hash/eq/ne values are used for caching and speed things up quite a bit.

  def __hash__(self):
    return id(self)

  def __eq__(self, other):
    return id(self) == id(other)

  def __ne__(self, other):
    return id(self) != id(other)

  def ASTeq(self, other):
    # Used in tests.
    return (self.constants == other.constants and
            self.type_params == other.type_params and
            self.classes == other.classes and
            self.functions == other.functions and
            self.aliases == other.aliases)


class Constant(node.Node('name', 'type')):
  __slots__ = ()


class Alias(node.Node('name', 'type')):
  """An alias (symbolic link) for a class implemented in some other module.

  Unlike Constant, the Alias is the same type, as opposed to an instance of that
  type. It's generated, among others, from imports - e.g. "from x import y as z"
  will create a local alias "z" for "x.y".
  """
  __slots__ = ()


class Class(node.Node('name', 'parents', 'methods', 'constants', 'template')):
  """Represents a class declaration.

  Used as dict/set key, so all components must be hashable.

  Attributes:
    name: Class name (string)
    parents: The super classes of this class (instances of pytd.TYPE).
    methods: Tuple of methods, classmethods, staticmethods
      (instances of pytd.Function).
    constants: Tuple of constant class attributes (instances of pytd.Constant).
    template: Tuple of pytd.TemplateItem instances.
  """
  # TODO(kramm): Rename "parents" to "bases". "Parents" is confusing since we're
  #              in a tree.

  __slots__ = ()

  def Lookup(self, name):
    """Convenience function: Look up a given name in the class namespace.

    Tries to find a method or constant by this name in the class.

    Args:
      name: Name to look up.

    Returns:
      A Constant or Function instance.

    Raises:
      KeyError: if this identifier doesn't exist in this class.
    """
    # TODO(kramm): Remove this. Make methods and constants dictionaries.
    try:
      return self._name2item[name]
    except AttributeError:
      self._name2item = {}
      for x in self.methods + self.constants:
        self._name2item[x.name] = x
      return self._name2item[name]


STATICMETHOD, CLASSMETHOD, METHOD = 'staticmethod', 'classmethod', 'method'


class Function(node.Node('name', 'signatures', 'kind')):
  """A function or a method, defined by one or more PyTD signatures.

  Attributes:
    name: The name of this function.
    signatures: Tuple of possible parameter type combinations for this function.
    kind: The type of this function. One of: STATICMETHOD, CLASSMETHOD, METHOD
  """
  __slots__ = ()


class ExternalFunction(Function):
  """A function or a method, defined by PYTHONCODE (see parse/parser.py).

  Attributes:
    name: The name of this function.
    signatures: Empty tuple of signatures.
  """
  __slots__ = ()


class Signature(node.Node('params', 'starargs', 'starstarargs',
                          'return_type', 'exceptions', 'template')):
  """Represents an individual signature of a function.

  For overloaded functions, this is one specific combination of parameters.
  For non-overloaded functions, there is a 1:1 correspondence between function
  and signature.

  Attributes:
    name: The name of this function.
    params: The list of parameters for this function definition.
    starargs: Name of the "*" parameter. The "args" in "*args".
    starstarargs: Name of the "*" parameter. The "kw" in "**kw".
    return_type: The return type of this function.
    exceptions: List of exceptions for this function definition.
    template: names for bindings for bounded types in params/return_type
  """
  __slots__ = ()

  @property
  def has_optional(self):
    return self.starargs is not None or self.starstarargs is not None


class Parameter(node.Node('name', 'type',
                          'kwonly', 'optional', 'mutated_type')):
  """Represents a parameter of a function definition.

  Attributes:
    name: The name of the parameter.
    type: The type of the parameter.
    kwonly: True if this parameter can only be passed as a keyword parameter.
    optional: If the parameter is optional.
    mutated_type: The type the parameter will have after the function is called
      if the type is mutated, None otherwise.
  """
  __slots__ = ()


class TypeParameter(node.Node('name', 'scope')):
  """Represents a type parameter.

  A type parameter is a bound variable in the context of a function or class
  definition. It specifies an equivalence between types.
  For example, this defines an identity function:
    def f<T>(x: T) -> T

  Attributes:
    name: Name of the parameter. E.g. "T".
    scope: Fully-qualified name of the class or function this parameter is
      bound to. E.g. "mymodule.MyClass.mymethod".
  """
  __slots__ = ()


class TemplateItem(node.Node('type_param')):
  """Represents template name for generic types.

  This is used for classes and signatures. The 'template' field of both is
  a list of TemplateItems. Note that *using* the template happens through
  TypeParameters.  E.g. in:
    class A<T>:
      def f(T x) -> T
  both the "T"s in the definition of f() are using pytd.TypeParameter to refer
  to the TemplateItem in class A's template.

  Attributes:
    type_param: the TypeParameter instance used. This is the actual instance
      that's used wherever this type parameter appears, e.g. within a class.
  """
  __slots__ = ()

  @property
  def name(self):
    return self.type_param.name


# Types can be:
# 1.) NamedType:
#     Specifies a type or import by name.
# 2.) NativeType
#     Points to a Python type. (int, float etc.)
# 3.) ClassType
#     Points back to a Class in the AST. (This makes the AST circular)
# 4.) GenericType
#     Contains a base type and parameters.
# 5.) UnionType / IntersectionType
#     Can be multiple types at once.
# 6.) NothingType / AnythingType
#     Special purpose types that represent nothing or everything.
# 7.) TypeParameter
#     A placeholder for a type.
# 8.) Scalar
#     A singleton type. Not currently used, but supported by the parser.
# For 1-3, the file visitors.py contains tools for converting between the
# corresponding AST representations.


class NamedType(node.Node('name')):
  """A type specified by name and, optionally, the module it is in."""
  __slots__ = ()

  def __str__(self):
    return self.name


class NativeType(node.Node('python_type')):
  """A type specified by a native Python type. Used during runtime checking."""
  __slots__ = ()


class ClassType(node.Node('name')):
  """A type specified through an existing class node."""

  # This type is different from normal nodes:
  # (a) It's mutable, and there are functions
  #     (parse/visitors.py:InPlaceFillInClasses) that modify a tree in place.
  # (b) Because it's mutable, it's not actually using the tuple/Node interface
  #     to store things (in particular, the pointer to the existing class).
  # (c) Visitors will not process the "children" of this node. Since we point
  #     to classes that are back at the top of the tree, that would generate
  #     cycles.

  __slots__ = ()

  def __new__(pycls, name, cls=None):  # pylint: disable=bad-classmethod-argument
    self = super(ClassType, pycls).__new__(pycls, name)
    # self.cls potentially filled in later (by visitors.InPlaceFillInClasses)
    self.cls = cls
    return self

  # __eq__ is inherited (using tuple equality + requiring the two classes
  #                      be the same)

  def __str__(self):
    return str(self.cls.name) if self.cls else self.name

  def __repr__(self):
    return '{type}{cls}({name})'.format(
        type=type(self).__name__, name=self.name,
        cls='<unresolved>' if self.cls is None else '')


class FunctionType(node.Node('name', 'function')):
  """The type of a function. E.g. the type of 'x' in 'x = lambda y: y'."""
  __slots__ = ()


class AnythingType(node.Node()):
  """A type we know nothing about yet ('?' in pytd)."""
  __slots__ = ()


class NothingType(node.Node()):
  """An "impossible" type, with no instances ('nothing' in pytd).

  Also known as the "uninhabited" type, or, in type systems, the "bottom" type.
  For representing empty lists, and functions that never return.
  """
  __slots__ = ()


class Scalar(node.Node('value')):
  __slots__ = ()


class UnionType(node.Node('type_list')):
  """A union type that contains all types in self.type_list."""
  __slots__ = ()

  # NOTE: type_list is kept as a tuple, to preserve the original order
  #       even though in most respects it acts like a frozenset.
  #       It also flattens the input, such that printing without
  #       parentheses gives the same result.

  def __new__(cls, type_list):
    assert type_list  # Disallow empty unions. Use NothingType for these.
    flattened = itertools.chain.from_iterable(
        t.type_list if isinstance(t, UnionType) else [t] for t in type_list)
    return super(UnionType, cls).__new__(cls, tuple(flattened))

  def __hash__(self):
    # See __eq__ - order doesn't matter, so use frozenset
    return hash(frozenset(self.type_list))

  def __eq__(self, other):
    if self is other:
      return True
    if isinstance(other, UnionType):
      # equality doesn't care about the ordering of the type_list
      return frozenset(self.type_list) == frozenset(other.type_list)
    return NotImplemented

  def __ne__(self, other):
    return not self == other


# TODO(kramm): Do we still need this?
class IntersectionType(node.Node('type_list')):
  """An intersection type that contains all types in self.type_list."""
  __slots__ = ()

  # NOTE: type_list is kept as a tuple, to preserve the original order
  #       even though in most respects it acts like a frozenset.
  #       It also flattens the input, such that printing without
  #       parentheses gives the same result.

  def __new__(cls, type_list):
    flattened = itertools.chain.from_iterable(
        t.type_list if isinstance(t, IntersectionType) else [t]
        for t in type_list)
    return super(IntersectionType, cls).__new__(cls, tuple(flattened))

  def __hash__(self):
    # See __eq__ - order doesn't matter, so use frozenset
    return hash(frozenset(self.type_list))

  def __eq__(self, other):
    if self is other:
      return True
    if isinstance(other, IntersectionType):
      # equality doesn't care about the ordering of the type_list
      return frozenset(self.type_list) == frozenset(other.type_list)
    return NotImplemented

  def __ne__(self, other):
    return not self == other


class GenericType(node.Node('base_type', 'parameters')):
  """Generic type. Takes a base type and type paramters.

  This corresponds to the syntax: type<type1,>, type<type1, type2> (etc.).

  Attributes:
    base_type: The base type. Instance of Type.
    parameters: Type parameters. Tuple of instances of Type.
  """
  __slots__ = ()


class HomogeneousContainerType(GenericType):
  """Special generic type for homogeneous containers. Only has one type param.

  This differs from GenericType in that it assumes *all* items in a container
  will be the same type. The syntax is type<t>. (Vs type<t,> for GenericType.)
  """
  __slots__ = ()

  @property
  def element_type(self):
    return self.parameters[0]


# So we can do "isinstance(node, pytd.TYPE)":
TYPE = (NamedType, NativeType, ClassType, AnythingType, UnionType,
        NothingType, GenericType, TypeParameter, Scalar,
        IntersectionType)

# Types that can be a base type of GenericType:
GENERIC_BASE_TYPE = (NamedType, ClassType)


def Print(n, print_format=None):
  """Convert a PYTD node to a string."""
  # TODO(kramm): fix circular import
  from pytype.pytd import utils  # pylint: disable=g-import-not-at-top
  return utils.Print(n, print_format)
