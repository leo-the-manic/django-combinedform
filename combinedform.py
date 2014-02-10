"""A utility class for combining several independent Django forms."""
from collections import defaultdict, Iterable
import functools
import sys

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import ForeignKey
from django import utils


class SubformError(BaseException):
    """An error occured when interacting with a subform."""
    pass


class Subform(object):
    """A container for a form constructor to include in a CombinedForm.

    This is a simple wrapper class.

    """

    # in order to allow CombinedForm to keep the user-declared ordering,
    # use this creation counter to assign a number to each Subform which can
    # be used to order them all
    #
    # Python gives all class instances in an unordered dict so maintaining the
    # declared order of fields must be done manually in this way
    __creation_counter = 0

    def __init__(self, subform_class, *args, **kwargs):
        """Store the subform's class as `formclass`."""
        self.args = args
        self.kwargs = kwargs
        self.formclass = subform_class
        self._ordering = Subform.__creation_counter
        Subform.__creation_counter += 1

    def make_instance(self, *args, **kwargs):
        """Create a new instance of this subform."""
        formargs = self.args + args
        kwargs.update(self.kwargs)
        return self.formclass(*formargs, **kwargs)


class CombinedFormMetaclass(type):
    """Allow a declarative style of CombinedForm generation."""

    def __init__(cls, name, bases, dct):
        """Find all subforms and collect them."""

        # scan class definition for Subform instances
        forms = {}
        ordernums_names = []  # use to sort Subforms by ordering number
        for attrname, attrval in dct.items():
            if isinstance(attrval, Subform):
                forms[attrname] = attrval.formclass
                ordernums_names.append((attrval._ordering, attrname))

        # keep track of subform declaration order
        formnames = [name for _, name in sorted(ordernums_names)]

        # anticipate inheritence; `cls` might be a derived class whose parent
        # class is also a CombinedForm; if so, the parent class' forms should
        # be included in the derived class' forms

        # get the next parent (which will have accumulated its parent, etc)
        is_formclass = lambda a: hasattr(a, '_forms')
        try:
            parent = next(base for base in bases if is_formclass(base))
        except StopIteration:
            pass
        else:

            # get all forms from parent class
            forms.update(parent._forms)

            # preserve form order from parent class
            formnames = parent._formnames + formnames

        # TODO: delete the `_forms` attribute, it is unneeded and prevents
        # users from overriding form factories if they need to
        cls._forms = forms
        cls._formnames = formnames
        super(CombinedFormMetaclass, cls).__init__(name, bases, dct)


def extract_subform_args(raw_kwargs, subform_names):
    """Sort kwargs into dicts organized by intended subform.

    This will only remove those arguments with keys matching the
    ``'subform__arg'`` pattern, and of those, only the ones where subform is a
    value in ``subform_names``.

    .. note:: All arguments extracted are also removed from ``raw_kwargs``
              as a side-effect

    :type  raw_kwargs: dict
    :param raw_kwargs: A dict with various ``'form__foo': 'bar'`` entries.

    :type  subform_names: seq
    :param subform_names: Subform names to recognize.

    :rtype:  dict of kwarg dicts

    Example:

    ::

        >>> ( extract_subform_args({'form1__foo': 'bar'}, ['form1']) ==
        ...   {'form1': {'foo': 'bar'}} )
        True

    """
    subform_args = defaultdict(dict)
    for raw_argname, argval in list(raw_kwargs.items()):
        if not '__' in raw_argname:
            continue
        formname, argname = raw_argname.split('__', 1)  # 1 is maxsplit
        if formname in subform_names:
            subform_args[formname][argname] = argval
            del raw_kwargs[raw_argname]
    return dict(subform_args)


class CombinedForm(object, metaclass=CombinedFormMetaclass):
    """A class which combines multiple forms.

    Inherit from this class and create class-level :py:class:`Subform` values
    for each form that you want to combine.

    Example:

    ::

        class MyCombinedForm(CombinedForm):

            form_a = Subform(FormA)

            form_b = Subform(FormB)

    Once this is done, if you have an instance like

    ::

        combinedform = MyCombinedForm()

    It will use the Subform values to construct subforms, so it will have
    values like

    ::

        combinedform.form_a
        combinedform.form_b

    Which would be instances of ``FormA`` and ``FormB``.

    **Options**

    To use an option field, simply create a class-level variable that follows
    the given description. There is right now only one specially recognized
    option field:

    ``main_form``

        A string, naming an attribute which is a :py:class:`Subform`. With this
        set, :py:meth:`save` will return what it got from the named subform,
        instead of its default behavior.

    """

    validators = tuple()  # default to no validators

    def __init__(self, *args, **kwargs):
        """Construct all subforms.

        Passes ``*args`` and ``**kwargs`` to all subforms, except for
        form-specific arguments.

        You can pass arguments to individual form constructors similarly to
        how you can filter on related object attributes to the ORM. In other
        words, a kwarg of

        ::

            subformname__arg='val'

        will translate into

        ::

            SubformConstructor(arg='val')

        """

        subform_args = extract_subform_args(kwargs, list(self.keys()))

        for subform_name in list(self.keys()):
            # check if we need to send subform args
            if subform_name in subform_args:
                kw = subform_args[subform_name]
                kw.update(kwargs)
            else:
                kw = kwargs

            form_factory = self[subform_name].make_instance
            try:
                form_inst = form_factory(*args, **kw)
                setattr(self, subform_name, form_inst)
            except BaseException as e:
                msg = ("Error creating {name} with args {args} and kwargs "
                       "{kwargs}: {msg}")
                error = msg.format(name=subform_name, args=args, kwargs=kw,
                                   msg=repr(e))
                raise SubformError(error).with_traceback(sys.exc_info()[2])

        self._errors = []  # for validation errors

    def keys(self):
        """Get a list of the names of all forms in this CombinedForm."""
        return list(self._formnames)  # send a copy to avoid breakage

    @property
    def errors(self):
        """Get all errors from subforms."""
        errors = {}
        for formname, form in self.iteritems():
            form_errors = form.errors

            # valid formsets will have e.g. errors = [{}, {}, {}] if there are
            # three forms in the formset. This means the combinedform errors
            # will be True. So sniff out that case and eliminate it
            if isinstance(form, forms.formsets.BaseFormSet):
                if not any(form_errors):
                    form_errors = None
            if form_errors:
                errors[formname] = form_errors
        return errors

    def __getitem__(self, k):
        """Allow access of subforms by self['subform_name'] syntax."""
        if k in list(self.keys()):
            return getattr(self, k)
        else:
            raise AttributeError("No subform with name '{}'".format(k))

    def __iter__(self):
        """Like dict, yield all keys to this CombinedForm instance."""
        return iter(list(self.keys()))

    def __unicode__(self):
        """Show all subforms with markup."""
        return self.as_p()
    def as_p(self):
        """Return all subforms as_p combined."""
        all_forms = ''.join(form.as_p() for form in list(self.values()))
        return utils.safestring.mark_safe(all_forms)

    def iteritems(self):
        """Iterate over the subform names and subforms."""
        return iter((k, self[k]) for k in list(self.keys()))

    def itervalues(self):
        """Iterate over the subforms."""
        return iter(self[k] for k in list(self.keys()))

    def values(self):
        """Get all subforms."""
        return list(self.itervalues())

    def forms_valid(self):
        """Check if all forms are valid as a whole.

        This will run all the validator methods defined in ``self.validators``

        """
        for validator in self.validators:
            try:
                validator(self)
            except TypeError as e:

                # check if the user gave a non-compliant validator, or if the
                # user's validator is throwing an exception itself
                if str(e).startswith(validator.__name__):
                    raise TypeError(str(e) + ". (Does your validator take"
                                    "one and only one argument?)")
                else:
                    raise
            except ValidationError as e:
                self._errors.extend(e.messages)
                return False
        return True

    @property
    def non_field_errors(self):
        """Get all non-field errors on all subforms and the CombinedForm.

        :rtype: list of strings

        """
        errorlist = list(self._errors)  # start with a copy of our own errors

        # add everyone else's errors
        for subform in self.values():

            try:
                subform.non_field_errors
            except AttributeError:

                # subform doesn't have non_field_errors, so try it as a
                # formset, which stores errors with a different name
                try:
                    subform.non_form_errors
                except AttributeError:

                    # subform doesn't quack like a duck
                    raise ValueError("Subform '{!r}' doesn't have attr "
                                     "'non_field_errors' or 'non_form_errors'"
                                     .format(subform))

                subform_errors = subform.non_form_errors()
            else:

                # don't catch an attr error raised during the call
                subform_errors = subform.non_field_errors()
            errorlist.extend(subform_errors)
        return errorlist

    def subforms_valid(self):
        """Test if all subforms are valid."""
        for formname, form in self.iteritems():
            try:
                if not form.is_valid():
                    return False
            except BaseException as exc:
                msg = "Error validating {name}: {msg}".format(name=formname,
                                                              msg=str(exc))
                raise SubformError(msg).with_traceback(sys.exc_info()[2])

        return all(f.is_valid() for f in self.values())

    def is_valid(self):
        """Test if all subforms, and all CombinedForm validators pass."""
        return self.subforms_valid() and self.forms_valid()

    #TODO: remove this
    def _modelformmap(self):
        return {(f.model if hasattr(f, 'model') else f._meta.model):
                (formname, self[formname])
                for formname, f in self.iteritems()}

    def save(self, commit=True, main_form=None):
        """Save all subforms.

        This will scan the forms for their dependencies and attempt to save
        them in an order such that they can all satisfy their dependencies.

        :type  commit: bool
        :param commit: Whether or not to write instances to the database.

        :type  main_form: str
        :param main_form:
            The name of the subform whose value is used as the final return
            value of ``save()``.

            - If ``None``, uses the value of the ``main_form`` instance or
              class variable. If neither exist, returns a dict.

            - If a non-``None`` falsy value, returns a dict even if
              ``main_form`` is set.

        :returns:
            Either a ``dict`` with subform names as keys and results of
            ``save()`` as values, or a single specified subform's ``save()``
            result. See ``main_form`` parameter documentation for more
            information.

        """
        assert self.is_valid()

        model_form_map = self._modelformmap()
        save_order = order_by_dependency(list(model_form_map.keys()))
        inst_map = {}
        formname_retval_map = {}
        for model in save_order:
            formname, form = model_form_map[model]

            try:
                inst = form.save(commit=False)
            except ValidationError as e:
                msg_tmpl = "Couldn't save {name}: {exc} (errors: {errors})"
                msg = msg_tmpl.format(name=type(form).__name__, exc=e,
                                      errors=form.errors)
                raise SubformError(msg).with_traceback(sys.exc_info()[2])

            inst_map[model] = inst

            # could be working with a form or a formset, so make a single
            # instance into a singleton list to allow the same code to work in
            # both cases
            original_inst = inst
            if not isinstance(inst, Iterable):
                inst = [inst]

            # link inst to previously created dependencies
            for dependency in get_model_dependencies(model, save_order):
                owner = inst_map[dependency.rel.to]

                for i in inst:
                    setattr(i, dependency.name, owner)

            # save to the database
            if commit:
                for i in inst:
                    i.save()
                if hasattr(form, 'save_m2m'):  # save other FKs if needed
                    form.save_m2m()

            # add to return values
            formname_retval_map[formname] = original_inst

        # decide whether to return one specific value or the dict
        if main_form is None:  # parameter unset, so try inst/class variable
            main_form = getattr(self, 'main_form', None)
        if main_form:
            return formname_retval_map[main_form]
        else:
            return formname_retval_map


def get_model_dependencies(model, relevant_models=None):
    """Get all ForeignKey fields on the given model `m`.

    If relevant_models is None, then get all ForeignKeys. If relevant_models
    is a collection, get only ForeignKeys which point to models it contains.
    """
    return (f for f in model._meta.fields if isinstance(f, ForeignKey)
            and f.rel.to in (relevant_models or [f.rel.to]))


def order_by_dependency(models):
    """Get a dependency sequence for the given models.

    :arg  models: The models to relate.
    :type models: seq

    :returns: A list in order from leaves (no depndencies) to root.

    """
    class Node(object):

        def __init__(self, model):
            self.model = model
            self.dependents = []

        def add_dependent(self, dep):
            self.dependents.append(dep)

        @property
        def depth(self):
            """Recursively calculate the depth of this node."""
            if self.dependents:
                return 1 + max(d.depth for d in self.dependents)
            else:
                return 0

        def __unicode__(self):
            mname = self.model.__name__
            dstr = ", ".join(d.model.__name__ for d in self.dependents)
            if not dstr: dstr = '[]'
            return "Node(model={}, dependents={})".format(mname, dstr)

        def __str__(self):
            return str(self.__unicode__())

        def __repr__(self):
            return str(self)

    def foreign_keys(m):
        """Get all ForeignKey fields on the given model `m`"""
        return (f for f in m._meta.fields if isinstance(f, ForeignKey))

    nodemap = {}
    def get_nodemap(key):
        """Get value at key, or if it doesn't exist create an empty Node."""
        val = nodemap.get(key, Node(key))
        nodemap[key] = val
        return val

    for model in models:
        self = get_nodemap(model)

        for fkfield in get_model_dependencies(model, models):
            fkmodel = fkfield.rel.to
            dependency = get_nodemap(fkmodel)
            dependency.add_dependent(self)

    # sort by reverse depth to get the models with no dependencies first
    sortedmodels = sorted(((n.depth, n.model) for n in nodemap.values()),
                          key=lambda tup: tup[0],  reverse=True)
    return [model for weight, model in sortedmodels]
