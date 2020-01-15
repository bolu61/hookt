from wrapt import ObjectProxy
from abc import ABC, abstractmethod

from anyio import create_task_group

class ABCTrigger(ABC):

    @property
    @abstractmethod
    def listeners(self):
        pass


    @abstractmethod
    def hook(self, callback):
        pass


    async def __call__(self, *args, **kwargs):
        r = await self.__wrapped__(*args, **kwargs)
        s = r if type(r) is tuple else (r,)
        async with create_task_group() as tg:
            for f in self.listeners:
                await tg.spawn(f, *s)
        return r



class DummyTrigger(ABCTrigger):

    def __init__(self):
        self._listeners = set()


    def __get__(self, instance, owner):
        return self


    @property
    def listeners(self):
        return self._listeners


    async def __call__(self):
        raise TypeError("Trigger has not been defined yet")



class Trigger(ABCTrigger, ObjectProxy):

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
        if instance or owner:
            self.__get__(instance, owner or type(instance)).hook(callback)
        else:
            self._self_listeners.add(callback)


    @property
    def listeners(self):
        return self._self_listeners



class BoundTrigger(ABCTrigger, ObjectProxy):

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
        def deco(f):
            if name in self._hashed_hooks:
                h = self._hashed_hooks[name]
                if isinstance(h, Trigger):
                    raise ValueError(f'Trigger "{name}" already defined')
                elif isinstance(h, DummyTrigger):
                    h = Trigger(f, h.listeners)
            else:
                self._hashed_hooks[name] = h = Trigger(f)
            return h
        return deco


    def hook(self, name, instance=None, owner=None):
        if name not in self._hashed_hooks:
            self._hashed_hooks[name] = h = DummyTrigger()
        else:
            h = self._hashed_hooks[name]

        return hook(h, instance, owner)



class BoundTriggerGroup(TriggerGroup):

    def __init__(self, instance, owner, hashed_hooks):
        self.instance = instance
        self.owner = owner
        self._hashed_hooks = hashed_hooks


    def __get__(self, instance, owner):
        return self


    def __getitem__(self, key):
        return super().__getitem__(key).__get__(self.instance, self.owner)


    def trigger(self, name, bind=False):
        def deco(f):
            if not bind:
                f = localfunction(f)
            if name in self._hashed_hooks:
                h = self._hashed_hooks[name]
                if isinstance(h, Trigger):
                    raise ValueError(f'Trigger "{name}" already defined')
                elif isinstance(h, DummyTrigger):
                    h = Trigger(f, h.listeners)
            else:
                self._hashed_hooks[name] = h = Trigger(f)
            return h.__get__(self.instance, self.owner)
        return deco


    def hook(self, name):
        return super().hook(name, self.instance, self.owner)



class localfunction(ObjectProxy):
    def __get__(self, instance=None, owner=None):
        return self

    def __call__(self, *args, **kwargs):
        return self.__wrapped__(*args, **kwargs)



class HooksMixin:

    hooks = None

    def trigger(self, name):
        return self.hooks.trigger(name)


    def hook(self, name):
        return self.hooks.hook(name)



def trigger(f):
    return Trigger(f)


def hook(h, instance=None, owner=None):
    if instance or owner:
        h = h.__get__(instance, owner or type(instance))

    def deco(f):
        h.hook(f)
        return f
    return deco
