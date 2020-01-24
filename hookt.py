from wrapt import ObjectProxy
from abc import ABC, abstractmethod

from anyio import create_task_group

__all__ = ["BaseTrigger", "Trigger", "TriggerGroup", "HooksMixin", "trigger", "hook"]

class BaseTrigger(ABC):
    """Trigger base class."""

    @property
    @abstractmethod
    def listeners(self):
        """Set of listeners."""
        pass


    @abstractmethod
    def hook(self, callback):
        """Register a callback.

        :param callback: asynchronous function that take as input the result of the trigger
        :type callback: function
        """
        pass


    async def __call__(self, *args, **kwargs):
        r = await self.__wrapped__(*args, **kwargs)
        s = r if type(r) is tuple else (r,)
        async with create_task_group() as tg:
            for f in self.listeners:
                await tg.spawn(f, *s)
        return r



class DummyTrigger(BaseTrigger):
    """Dummy trigger for internal use"""

    def __init__(self):
        self._listeners = set()


    def __get__(self, instance, owner):
        return self


    @property
    def listeners(self):
        return self._listeners


    async def __call__(self):
        raise TypeError("Trigger has not been defined yet")



class Trigger(BaseTrigger, ObjectProxy):
    """Trigger that calls registered hooks after execution.

    :param func: the function to set as trigger
    :type func: function
    :param listeners: a set of listeners, defaults to None
    :type listeners: set, optional
    """

    def __init__(self, func, listeners=None):
        super().__init__(func)
        self._self_listeners = listeners or set()
        self._self_instance_listeners = None


    def __get__(self, instance, owner):
        if not instance:
            return self

        if not self._self_instance_listeners:
            self._self_instance_listeners = {instance: set()}

        elif instance not in self._self_instance_listeners:
            self._self_instance_listeners[instance] = set()

        return BoundTrigger(
            func = self.__wrapped__.__get__(instance, owner),
            listeners = self._self_instance_listeners[instance],
            class_listeners = self._self_listeners
        )


    def hook(self, callback, instance=None, owner=None):
        """Register a callback

        :param callback: asynchronous function that takes as input the result of the trigger
        :type callback: function
        """
        if instance or owner:
            self.__get__(instance, owner or type(instance)).hook(callback)
        else:
            self._self_listeners.add(callback)


    @property
    def listeners(self):
        """Set of listeners"""
        return self._self_listeners



class BoundTrigger(BaseTrigger, ObjectProxy):
    """A trigger bound to an instance.

    This class should not be created directly in normal circumstances.
    """

    def __init__(self, func, listeners, class_listeners):
        super().__init__(func)
        self._self_listeners = listeners
        self._self_class_listeners = class_listeners


    def __get__(self, instance, owner):
        return self


    @property
    def listeners(self):
        return self._self_listeners | self._self_class_listeners


    def hook(self, callback):
        self._self_listeners.add(callback)



class TriggerGroup(object):
    """A group for named triggers

    A trigger group can be used on its own or as a class member.
    In the latter case, referencing it from an instance will use that instance's
    group, which inherits from the class group.
    """

    def __init__(self):
        self._hashed_hooks = {}


    def __get__(self, instance, owner):
        if not instance:
            return self

        return BoundTriggerGroup(instance, owner, self._hashed_hooks)


    def __contains__(self,key):
        return self._hashed_hooks.__contains__(key)


    def __getitem__(self, key):
        return self._hashed_hooks.__getitem__(key)


    def __setitem__(self, key, value):
        return self._hashed_hooks.__setitem__(key, value)


    def trigger(self, name):
        """Decorate an asynchronous function as a named trigger.

        :param name: the name of the trigger.
        :type name: str
        :raises ValueError: raised when the name is already defined for another trigger.
        """
        def deco(f):
            if name in self._hashed_hooks:
                f = self._hashed_hooks[name]
                if isinstance(h, Trigger):
                    raise ValueError(f'Trigger "{name}" already defined')
                elif isinstance(h, DummyTrigger):
                    f = Trigger(f, h.listeners)
            else:
                self._hashed_hooks[name] = f = Trigger(f)
            return f
        return deco


    def hook(self, name, instance=None, owner=None):
        """Decorate am asynchronous function to register it as a callback.

        Function registered on triggers will be called everytime the triggers are
        executed, regardless of the instance they are bound to.

        :param name: the name of the trigger to be hooked on
        :type name: str
        """
        if name not in self._hashed_hooks:
            self._hashed_hooks[name] = h = DummyTrigger()
        else:
            h = self._hashed_hooks[name]

        return hook(h, instance, owner)



class BoundTriggerGroup(TriggerGroup):
    """A TriggerGroup bound to an instance

    This class should not be created directly under normal circumstances.
    """

    def __init__(self, instance, owner, hashed_hooks):
        self.instance = instance
        self.owner = owner
        self._hashed_hooks = hashed_hooks


    def __get__(self, instance, owner):
        return self


    def __getitem__(self, key):
        return super().__getitem__(key).__get__(self.instance, self.owner)


    def hook(self, name, instance=None, owner=None):
        """Decorate am asynchronous function to register it as a callback.

        Functions registered on triggers bound to this instance will not be called when
        the same triggers bound to other instances are executed.

        :param name: the name of the trigger to be hooked on
        :type name: str
        """
        return super().hook(name, instance or self.instance, owner or self.owner)



class HooksMixin:

    hooks = None

    def trigger(self, name):
        return self.hooks.trigger(name)


    def hook(self, name):
        return self.hooks.hook(name)



def trigger(f):
    """Create a trigger from an asynchronous function.

    :param f: the function to set as a trigger
    :type f: function
    :return: a trigger
    :rtype: class:`Trigger`
    """
    return Trigger(f)


def hook(t, instance=None, owner=None):
    """Decorate a function to be registered on a trigger

    :param t: the trigger to register the function on
    :type t: class:`Trigger`
    """
    if instance or owner:
        t = t.__get__(instance, owner or type(instance))

    def deco(f):
        t.hook(f)
        return f
    return deco
