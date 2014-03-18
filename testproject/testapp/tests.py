"""Tests for the CombinedForm utilitiy class."""
import unittest
from unittest import mock

import django.test
from django import forms
from django.db import models

import combinedform


class CombinedFormTest(unittest.TestCase):
    """Tests for the CombinedForm utility class."""

    def test_keys(self):
        """Test that the `keys` method works as expected."""

        class MyCombinedForm(combinedform.CombinedForm):
            form1 = combinedform.Subform(mock.MagicMock)

        inst = MyCombinedForm()
        self.assertEqual(list(inst.keys()), ['form1'])

    def test_subform_arguments(self):
        """subform__arg will get sent to the right subform."""
        subform_mock = mock.MagicMock()

        class MyCombinedForm(combinedform.CombinedForm):
            form1 = combinedform.Subform(subform_mock)

        MyCombinedForm(form1__foo='bar')
        subform_mock.assert_called_with(foo='bar')

    def test_subform_arguments_not_sent_elsewhere(self):
        """A subform argument doesn't get sent to an unintended subform."""
        subform_a = mock.MagicMock()
        subform_b = mock.MagicMock()

        class Combined(combinedform.CombinedForm):
            form1 = combinedform.Subform(subform_a)
            form2 = combinedform.Subform(subform_b)

        Combined(form2__foo='bar')
        subform_a.assert_called_with()

    def test_global_args(self):
        """Arguments get sent to all subforms."""
        subform_a = mock.MagicMock()
        subform_b = mock.MagicMock()

        class Combined(combinedform.CombinedForm):
            form1 = combinedform.Subform(subform_a)
            form2 = combinedform.Subform(subform_b)

        Combined(foo='bar')
        subform_a.assert_called_with(foo='bar')
        subform_b.assert_called_with(foo='bar')

    def test_errors(self):
        """errors collects subform errors."""
        subform_a = mock.MagicMock()
        subform_a().errors = {'foo_field': 'Not enough bars'}
        subform_b = mock.MagicMock()
        subform_b().errors = {'bar_field': 'Not enough foos'}

        class Combined(combinedform.CombinedForm):
            form1 = combinedform.Subform(subform_a)
            form2 = combinedform.Subform(subform_b)

        c = Combined()
        expected_errors = {'form1': {'foo_field': 'Not enough bars'},
                           'form2': {'bar_field': 'Not enough foos'}}
        self.assertEqual(c.errors, expected_errors)

    def test_combinedform_validators_called(self):
        """Validators for the completed formset get called."""
        validate_stuff = mock.MagicMock()

        class Form(combinedform.CombinedForm):
            validators = [validate_stuff]

        inst = Form()
        inst.forms_valid()
        validate_stuff.assert_called_with(inst)

        validator1, validator2 = mock.MagicMock(), mock.MagicMock()

        class Form2(combinedform.CombinedForm):
            validators = [validator1, validator2]

        inst = Form2()
        inst.forms_valid()
        validator1.assert_called_with(inst)
        validator2.assert_called_with(inst)

    def test_forms_valid_when_no_validators(self):
        """When there are no validators, forms_valid() is True."""

        class Form(combinedform.CombinedForm):
            pass

        inst = Form()
        self.assertTrue(inst.forms_valid())

    def test_validator_raises_means_forms_invalid(self):
        """When a validator raises ValidationError, forms_valid() is False."""
        validator = mock.MagicMock(side_effect=forms.ValidationError("Invalid"))

        class Combined(combinedform.CombinedForm):
            validators = [validator]

        inst = Combined()
        self.assertFalse(inst.forms_valid())

    def test_validator_exceptions_added_to_errorlist(self):
        """When a validator raises ValidationError, its message is stored."""
        validator = mock.MagicMock(side_effect=forms.ValidationError("Invalid"))

        class Combined(combinedform.CombinedForm):
            validators = [validator]

        inst = Combined()
        inst.forms_valid()
        self.assertEqual(inst.non_field_errors, ['Invalid'])

    def test_iterator_returns_keys(self):
        """The iterator yields the subform names."""
        form_a = mock.MagicMock()

        class Combined(combinedform.CombinedForm):
            form1 = combinedform.Subform(form_a)

        iter_vals = list(iter(Combined()))
        self.assertEqual(iter_vals, ['form1'])

        form_b = mock.MagicMock()

        class Combined2(combinedform.CombinedForm):
            form1 = combinedform.Subform(form_a)
            form2 = combinedform.Subform(form_b)

        iter_vals2 = list(iter(Combined2()))
        self.assertEqual(iter_vals2, ['form1', 'form2'])

    def test_subforms_valid(self):
        """subforms_valid() is True if all subforms are valid."""
        subform_a = mock.MagicMock()
        subform_a.is_valid.return_value = True

        class Combined(combinedform.CombinedForm):
            form1 = combinedform.Subform(subform_a)

        self.assertTrue(Combined().subforms_valid())

    def test_invalid_subform_subforms_invalid(self):
        """subforms_valid() is False if a subform is invalid."""
        subform_a = mock.MagicMock()
        subform_a().is_valid.return_value = False

        class Combined(combinedform.CombinedForm):
            form1 = combinedform.Subform(subform_a)

        self.assertFalse(Combined().subforms_valid())

    def test_is_valid_true_when_all_valid(self):
        """is_valid() is True if subforms and CombinedForm are both valid."""

        class Combined(combinedform.CombinedForm):
            validators = [mock.MagicMock()]
            form1 = combinedform.Subform(mock.MagicMock())

        self.assertTrue(Combined().is_valid())

    def test_is_valid_false_on_bad_validator(self):
        """is_valid() is False if CombinedForm validator is false."""

        class Combined(combinedform.CombinedForm):
            validators = [
                mock.MagicMock(side_effect=forms.ValidationError('a'))]
            form1 = combinedform.Subform(mock.MagicMock())

        self.assertFalse(Combined().is_valid())

    def test_is_valid_false_on_bad_subform(self):
        """is_valid() is False if a subform's is_valid() is False."""
        subform = mock.MagicMock()
        subform().is_valid.return_value = False

        class Combined(combinedform.CombinedForm):
            validators = [mock.MagicMock()]
            form1 = combinedform.Subform(subform)

        self.assertFalse(Combined().is_valid())

    def test_is_valid_true_for_empty_inst(self):
        """A CombinedForm with no validators or subforms is valid."""

        class Combined(combinedform.CombinedForm):
            pass

        self.assertTrue(Combined().is_valid())

    def test_non_field_errors_gets_subform_errors(self):
        """non_field_errors gets all nonfield errors from subforms."""
        subform = mock.MagicMock()
        subform().non_field_errors.return_value = ['foo']

        class Combined(combinedform.CombinedForm):
            form1 = combinedform.Subform(subform)

        self.assertEqual(Combined().non_field_errors, ['foo'])

    def test_non_field_errors_gets_formsets(self):
        """non_field_errors can handle formsets."""
        formset = mock.MagicMock()
        del formset().non_field_errors
        formset().non_form_errors.return_value = ['foo']

        class Combined(combinedform.CombinedForm):
            form1 = combinedform.Subform(formset)

        self.assertEqual(Combined().non_field_errors, ['foo'])

    def test_validator_args_errormessage(self):
        """A validator with the wrong signature gets a helpful message."""
        validator = lambda: None

        class Combined(combinedform.CombinedForm):
            validators = [validator]

        try:
            Combined().is_valid()
        except TypeError as e:
            self.assertIn('Does your validator', str(e))

    def test_validator_raising_typeerror_left_alone(self):
        """A validator which raises a TypeError doesn't get swallowed."""

        def validator(form):
            raise TypeError("Foo")

        class Combined(combinedform.CombinedForm):
            validators = [validator]

        try:
            Combined().is_valid()
        except TypeError as e:
            self.assertNotIn("Does your validator", str(e))

    def test_empty_formset_doesnt_propgate_empty_errors(self):
        """A formset with no errors returns an empty error result."""

        class MyModel(models.Model):
            a = models.CharField(max_length=10)
            b = models.CharField(max_length=10)

        class MyForm(forms.ModelForm):
            class Meta:
                model = MyModel
                fields = ('b',)

        MyFormSet = forms.formsets.formset_factory(MyForm)
        data = {'form-0-b': '1', 'form-1-b': '2', 'form-1-b': '3',
                'form-INITIAL_FORMS': '0', 'form-TOTAL_FORMS': '3',
                'form-MAX_NUM_FORMS': '1000'}

        class MyCombinedForm(combinedform.CombinedForm):
            myform = combinedform.Subform(MyFormSet)

        print(MyCombinedForm().myform)
        combined = MyCombinedForm(data)
        self.assertEqual(combined.errors, {})
        self.assertEqual(combined.non_field_errors, [])


class OrderByDependencyTest(unittest.TestCase):
    """Tests for the order_by_dependency function.

    In order to make the test output less ridiculous to read, a "stringify"
    method is used to refer to models just by their unqiue digit.

    .. warning::

        Django's ORM has some kind of global namespace problem, and doesn't
        clean that namespace between test runs, so the models can't all be
        named Model1, Model2 etc. between test cases.
    """

    def stringify(self, seq):
        """Convert lists of models named ModelN to just strings of Ns.

        N is an integer. Leading zeroes are removed from N.

        """

        def reduce_to_number(s):
            """Reduce a string "a0b1" to "1".

            Removes alphabetic characters as well as leading zeroes.

                >>> reduce_to_number("a1b2c3")
                "123"
                >>> reduce_to_number("q0b2x0")
                "20"

            """
            digits = (c for c in s if c.isdigit())
            num_str = ''.join(digits)
            return num_str.lstrip('0')  # remove leading zeroes

        return " ".join(reduce_to_number(str(e)) for e in seq)

    def test_basic_foreignkey(self):
        """Properly orders a basic foreign key relationship."""

        class Model1(models.Model):
            pass

        class Model2(models.Model):
            m1 = models.ForeignKey(Model1)

        result = combinedform.order_by_dependency([Model2, Model1])
        self.assertEqual(self.stringify(result), "1 2")

        class Model3(models.Model):
            pass

        class Model4(models.Model):
            m3 = models.ForeignKey(Model3)

        result = combinedform.order_by_dependency([Model3, Model4])
        self.assertEqual(self.stringify(result), "3 4")

    def test_second_level_fks(self):
        """Test a set of foreign key relations two levels deep."""

        class Model01(models.Model):            # A visual:
            pass                                #

        class Model02(models.Model):            # m4
            m1 = models.ForeignKey(Model01)     #  \

        class Model03(models.Model):            #   m2   m3
            m1 = models.ForeignKey(Model01)     #    \  /

        class Model04(models.Model):            #     m1
            m2 = models.ForeignKey(Model02)

        result = combinedform.order_by_dependency(
            [Model03, Model02, Model04, Model01])

        # there are two equivalent possibilities
        # also convert to strings because it's way easier to read the output
        result = self.stringify(result)
        self.assertIn(result, ["1 2 3 4", "1 2 4 3"])

    def test_ignores_externals(self):
        """The ordering doesn't account for models not given as arguments."""

        class Model001(models.Model):           # A visual:
            pass                                #

        class Model002(models.Model):           # m1   m2
            pass                                #  \  /

        class Model003(models.Model):           #   m3
            m1 = models.ForeignKey(Model001)    #   /
            m2 = models.ForeignKey(Model002)    # m4

        class Model004(models.Model):
            m3 = models.ForeignKey(Model003)

        # add extra models to artifically add depth to Model3 that's not
        # relevant for the subgraph we're interested in; test if it is properly
        # ignored
        class ModelA(models.Model):
            m3 = models.ForeignKey(Model003)

        class ModelB(models.Model):
            ma = models.ForeignKey(ModelA)

        class ModelC(models.Model):
            mb = models.ForeignKey(ModelB)

        result = combinedform.order_by_dependency(
            [Model003, Model002, Model004, Model001])
        result = self.stringify(result)
        self.assertIn(result, ["1 2 3 4", "2 1 3 4"])


class CombinedFormIntegrationTest(django.test.TestCase):
    """Test the features of CombinedForm which use the database."""

    def test_dependency_saving(self):
        """Test models are saved in a safe order and properly linked."""
        from django.db.models import CharField
        from django.forms import ModelForm
        from django.forms.models import inlineformset_factory

        class ModelFoo(models.Model):
            description = CharField(max_length=20)

        class ModelBar(models.Model):
            name = CharField(max_length=20)
            foo = models.ForeignKey(ModelFoo)

        class ModelBuzz(models.Model):
            title = CharField(max_length=20)
            bar = models.ForeignKey(ModelBar)

        class FooForm(ModelForm):
            class Meta:
                model = ModelFoo
                fields = ('description',)

        class BarForm(ModelForm):
            class Meta:
                model = ModelBar
                fields = ('name',)

        class BuzzForm(ModelForm):
            class Meta:
                model = ModelBuzz
                fields = ('title',)

        BuzzFormset = inlineformset_factory(ModelBar, ModelBuzz, form=BuzzForm,
                                            can_delete=False)

        class TheForm(combinedform.CombinedForm):
            # models are given backwards just to ensure it doesn't accidentally
            # save in the intended order
            buzz = combinedform.Subform(BuzzFormset)
            bar = combinedform.Subform(BarForm)
            foo = combinedform.Subform(FooForm)

        formdata = {'description': 'an', 'name': 'i',
                    'modelbuzz_set-0-title': 'yo',
                    'modelbuzz_set-1-title': 'dawg',
                    'modelbuzz_set-TOTAL_FORMS': 3,
                    'modelbuzz_set-INITIAL_FORMS': 0,
                    'modelbuzz_set-MAX_NUM_FORMS': 1000, }
        inst = TheForm(formdata)
        self.assertTrue(inst.is_valid())

        saved = inst.save(commit=False) # can't do a real save on above models
        buzz = saved['buzz'][0]
        self.assertIsInstance(buzz, ModelBuzz)
        self.assertEqual(buzz.title, 'yo')
        self.assertTrue(isinstance(buzz.bar, ModelBar))
        self.assertEqual(buzz.bar.name, 'i')
        self.assertTrue(isinstance(buzz.bar.foo, ModelFoo))
        self.assertEqual(buzz.bar.foo.description, 'an')


class MainFormTest(unittest.TestCase):
    """Tests for ``main_form`` attribute of py:class:`CombinedForm`."""

    def mockmodelform(self):
        """Make a mock ModelForm."""
        form = mock.MagicMock(spec=forms.ModelForm)
        model = mock.MagicMock(spec=models.Model)
        form.return_value.save.return_value = model
        return form

    def test_save_obeys_main_form(self):
        """The save() method will proxy the value of 'main_form' if set."""
        MyModelForm = self.mockmodelform()

        class MyCombinedForm(combinedform.CombinedForm):
            form_a = combinedform.Subform(MyModelForm)
            form_b = combinedform.Subform(self.mockmodelform())
            main_form = 'form_a'

        form = MyCombinedForm()
        self.assertEqual(form.save(), MyModelForm().save())

    def test_save_returns_map_with_no_main(self):
        """If main_class is not set, save() returns a map."""

        class MyCombinedForm(combinedform.CombinedForm):
            form_a = combinedform.Subform(self.mockmodelform())
            form_b = combinedform.Subform(self.mockmodelform())

        form = MyCombinedForm()
        self.assertEqual(set(form.save().keys()), set(['form_a', 'form_b']))
