from JumpscaleCoreLib.baseclasses.JSBase import JSBase


class JSFactory(JSBase):
    def _init_factory(self, **kwargs):

        # these are classes which will be created automatically when the factory class starts
        if hasattr(self.__class__, "_CHILDCLASSES"):
            for kl in self.__class__._CHILDCLASSES:
                # childclasses are the e.g. JSConfigs classes
                if "name" not in kwargs:
                    obj = kl(parent=self, name="main", **kwargs)
                else:
                    obj = kl(parent=self, **kwargs)
                name = obj._name
                obj.name = name
                assert name
                assert obj._parent
                self.__children[name] = obj

    def _children_names_get(self, filter=None):
        r = [str(i) for i in self.__children.keys()]
        return self._filter(filter=filter, llist=r)

    def _childclass_selector(self, **kwargs):
        return self.__class__._CHILDCLASS

    def _obj_cache_reset(self):
        """
        make sure that all objects we remember inside are emptied
        :return:
        """
        JSBase._obj_cache_reset(self)
        for factory in self.__children.values():
            factory._obj_cache_reset()

    def reset(self):
        """
        careful is a very dangerous function, will delete all children (call reset and delete on each child)
        if there is a config object attached to it, it will also delete it

        :return:
        """
        self.delete()

    def save(self):
        for item in self.__children_get():
            if isinstance(item, j.baseclasses.object):
                if item._hasattr("save"):
                    item.save()
            else:
                raise j.exceptions.JSBUG("only suport j.baseclasses.object")

    def get(self, name="main", needexist=False, autosave=True, reload=False, **kwargs):
        """

        :param name: of the child to get, if it doesn't need to exist then will try to create new
        new one can only be created if self.__class__._CHILDCLASS has been set


        """
        name = name.replace("__", ".")
        child = self._validate_child(name)
        if not child:
            if hasattr(self.__class__, "_CHILDCLASS") and needexist is False:
                self.new(name=name, autosave=autosave, **kwargs)
            else:
                raise j.exceptions.Value(f"cannot get child with name:{name} on {self._key}")
        if reload:
            self.__children[name].load()
        return self.__children[name]

    def find(self, **kwargs):
        """
        :param kwargs: e.g. color="red",...
        :return: list of the children objects found
        """
        res = []
        for key, item in self.__children.items():
            match = True
            if isinstance(item, j.baseclasses.object_config):
                for key, val in kwargs.items():
                    print("need to check in properties of schema to see if we can check")
                    j.shell()
            elif isinstance(item, j.baseclasses.object):
                for key, val in kwargs.items():
                    if item._hasattr(key):
                        if val != getattr(item, key):
                            match = False
                    else:
                        raise j.exceptions.Value("could not find for prop:%s, did not exist in %s" % (key, self._key))
            else:
                raise j.exceptions.JSBUG("only support jsx objects in _children")
            if match:
                res.append(item)
        return res

    # def count(self, name):
    #     """
    #     :param kwargs: e.g. color="red",...
    #     :return: list of the config objects
    #     """
    #     raise j.exceptions.NotImplemented()
    #     # r = 0
    #     # if name in self.__children:
    #     #     child = self.__children[name]
    #     #     if self._hasattr(child, "count"):
    #     #         r += child.count(name=name)

    def delete(self, name=None):
        """

        :param name:
        :return:
        """
        self._delete(name=name)

    def _delete(self, name=None):
        if name:
            child = self._validate_child(name)
            if child:
                child.delete()
        else:
            self.__children_delete()

        if self.__parent:
            # if we exist in the parent remove us from their children
            if self._classname in self.__parent._children:
                self.__parent._children.pop(self._classname)

    def exists(self, name="main"):
        """
        :param name: of the object
        """
        child = self._validate_child(name)
        if child:
            return True
