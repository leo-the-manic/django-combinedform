"""Tests for the CombinedForm utilitiy class."""
import datetime
import unittest
import unittest.mock

import django.db.models
import django.forms
import django.test
import django.utils.timezone

import combinedform


class CombinedFormTest(unittest.TestCase):
    """Tests for the CombinedForm utility class."""

    def test_keys(self):
        """Test that the `keys` method works as expected."""

        class MyCombinedForm(combinedform.CombinedForm):
            form1 = combinedform.Subform(unittest.mock.MagicMock)

        inst = MyCombinedForm()
        self.assertEqual(list(inst.keys()), ['form1'])

    def test_subform_arguments(self):
        """subform__arg will get sent to the right subform."""
        subform_mock = unittest.mock.MagicMock()

        class MyCombinedForm(combinedform.CombinedForm):
            form1 = combinedform.Subform(subform_mock)

        MyCombinedForm(form1__foo='bar')
        subform_mock.assert_called_with(foo='bar')

    def test_subform_arguments_not_sent_elsewhere(self):
        """A subform argument doesn't get sent to an unintended subform."""
        subform_a = unittest.mock.MagicMock()
        subform_b = unittest.mock.MagicMock()

        class Combined(combinedform.CombinedForm):
            form1 = combinedform.Subform(subform_a)
            form2 = combinedform.Subform(subform_b)

        Combined(form2__foo='bar')
        subform_a.assert_called_with()

    def test_global_args(self):
        """Arguments get sent to all subforms."""
        subform_a = unittest.mock.MagicMock()
        subform_b = unittest.mock.MagicMock()

        class Combined(combinedform.CombinedForm):
            form1 = combinedform.Subform(subform_a)
            form2 = combinedform.Subform(subform_b)

        Combined(foo='bar')
        subform_a.assert_called_with(foo='bar')
        subform_b.assert_called_with(foo='bar')

    def test_errors(self):
        """errors collects subform errors."""
        subform_a = unittest.mock.MagicMock()
        subform_a().errors = {'foo_field': 'Not enough bars'}
        subform_b = unittest.mock.MagicMock()
        subform_b().errors = {'bar_field': 'Not enough foos'}

        class Combined(combinedform.CombinedForm):
            form1 = combinedform.Subform(subform_a)
            form2 = combinedform.Subform(subform_b)

        c = Combined()
        expected_errors = {'form1': {'foo_field': 'Not enough bars'},
                           'form2': {'bar_field': 'Not enough foos'}}
        self.assertEqual(c.errors, expected_errors)

    def test_errors_go_to_subform(self):
        """combinedform errors can be assigned to subform fields."""

        def my_validator(form):
            raise combinedform.FieldValidationError('my_form',
                                                    {'my_field': ['foo']})

        class MyForm(django.forms.Form):
            my_field = django.forms.CharField(required=False)

        class MyCombinedForm(combinedform.CombinedForm):
            my_form = combinedform.Subform(MyForm)

            validators = (my_validator,)

        # ensure the subform alone is valid
        subform = MyForm({})
        self.assertTrue(subform.is_valid())

        form = MyCombinedForm({})
        self.assertFalse(form.is_valid())
        self.assertEqual(['foo'], form.my_form.errors['my_field'])

    def test_combinedform_validators_called(self):
        """Validators for the completed formset get called."""
        validate_stuff = unittest.mock.MagicMock()

        class Form(combinedform.CombinedForm):
            validators = [validate_stuff]

        inst = Form()
        inst.forms_valid()
        validate_stuff.assert_called_with(inst)

        validator1 = unittest.mock.MagicMock()
        validator2 = unittest.mock.MagicMock()

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
        error = django.forms.ValidationError("Invalid")
        validator = unittest.mock.MagicMock(side_effect=error)

        class Combined(combinedform.CombinedForm):
            validators = [validator]

        inst = Combined()
        self.assertFalse(inst.forms_valid())

    def test_validator_exceptions_added_to_errorlist(self):
        """When a validator raises ValidationError, its message is stored."""
        error = django.forms.ValidationError("Invalid")
        validator = unittest.mock.MagicMock(side_effect=error)

        class Combined(combinedform.CombinedForm):
            validators = [validator]

        inst = Combined()
        inst.forms_valid()
        self.assertEqual(inst.non_field_errors, ['Invalid'])

    def test_iterator_returns_keys(self):
        """The iterator yields the subform names."""
        form_a = unittest.mock.MagicMock()

        class Combined(combinedform.CombinedForm):
            form1 = combinedform.Subform(form_a)

        iter_vals = list(iter(Combined()))
        self.assertEqual(iter_vals, ['form1'])

        form_b = unittest.mock.MagicMock()

        class Combined2(combinedform.CombinedForm):
            form1 = combinedform.Subform(form_a)
            form2 = combinedform.Subform(form_b)

        iter_vals2 = list(iter(Combined2()))
        self.assertEqual(iter_vals2, ['form1', 'form2'])

    def test_subforms_valid(self):
        """subforms_valid() is True if all subforms are valid."""
        subform_a = unittest.mock.MagicMock()
        subform_a.is_valid.return_value = True

        class Combined(combinedform.CombinedForm):
            form1 = combinedform.Subform(subform_a)

        self.assertTrue(Combined().subforms_valid())

    def test_invalid_subform_subforms_invalid(self):
        """subforms_valid() is False if a subform is invalid."""
        subform_a = unittest.mock.MagicMock()
        subform_a().is_valid.return_value = False

        class Combined(combinedform.CombinedForm):
            form1 = combinedform.Subform(subform_a)

        self.assertFalse(Combined().subforms_valid())

    def test_is_valid_true_when_all_valid(self):
        """is_valid() is True if subforms and CombinedForm are both valid."""

        class Combined(combinedform.CombinedForm):
            validators = [unittest.mock.MagicMock()]
            form1 = combinedform.Subform(unittest.mock.MagicMock())

        self.assertTrue(Combined().is_valid())

    def test_is_valid_false_on_bad_validator(self):
        """is_valid() is False if CombinedForm validator is false."""
        error = django.forms.ValidationError('a')

        class Combined(combinedform.CombinedForm):
            validators = [
                unittest.mock.MagicMock(side_effect=error)]
            form1 = combinedform.Subform(unittest.mock.MagicMock())

        self.assertFalse(Combined().is_valid())

    def test_is_valid_false_on_bad_subform(self):
        """is_valid() is False if a subform's is_valid() is False."""
        subform = unittest.mock.MagicMock()
        subform().is_valid.return_value = False

        class Combined(combinedform.CombinedForm):
            validators = [unittest.mock.MagicMock()]
            form1 = combinedform.Subform(subform)

        self.assertFalse(Combined().is_valid())

    def test_is_valid_true_for_empty_inst(self):
        """A CombinedForm with no validators or subforms is valid."""

        class Combined(combinedform.CombinedForm):
            pass

        self.assertTrue(Combined().is_valid())

    def test_non_field_errors_gets_subform_errors(self):
        """non_field_errors gets all nonfield errors from subforms."""
        subform = unittest.mock.MagicMock()
        subform().non_field_errors.return_value = ['foo']

        class Combined(combinedform.CombinedForm):
            form1 = combinedform.Subform(subform)

        self.assertEqual(Combined().non_field_errors, ['foo'])

    def test_provides_combined_cleaned_data(self):
        """Provides a combined cleaned data attribute."""
        RadioSelect = django.forms.RadioSelect

        class YesNoForm(django.forms.Form):
            val = django.forms.TypedChoiceField(((True, 'Yes'), (False, 'No')),
                                                coerce=lambda v: v == 'Yes',
                                                widget=RadioSelect)

        class MyForm(combinedform.CombinedForm):
            yesno = combinedform.Subform(YesNoForm, prefix='yesno')

        f = MyForm({'yesno-val': 'Yes'})
        self.assertTrue(f.is_valid(), f.errors)
        self.assertEqual({'yesno': {'val': True}}, f.cleaned_data)

        class TimeForm(django.forms.Form):
            time = django.forms.DateTimeField()

        class MyForm2(combinedform.CombinedForm):
            event = combinedform.Subform(TimeForm, prefix='event')

        f = MyForm2({'event-time': '4/5/2010 3:30'})
        self.assertTrue(f.is_valid(), f.errors)

        expected_time = datetime.datetime(year=2010, month=4, day=5, hour=3,
                                          minute=30)

        # django attaches a tz so attach to expected data, too
        tz = django.utils.timezone
        expected_time = tz.make_aware(expected_time, tz.get_default_timezone())
        expected_data = {
            'event': {'time': expected_time},
        }

        self.assertEqual(expected_data, f.cleaned_data)

    def test_cleaneddata_without_prefix(self):
        """cleaned_data operates on prefix-less subforms."""
        class MyForm(django.forms.Form):
            my_field = django.forms.CharField()

        class MyCombined(combinedform.CombinedForm):
            form = combinedform.Subform(MyForm)

        combined = MyCombined({'my_field': 'foo'})
        assert combined.is_valid()
        self.assertEqual({'form': {'my_field': 'foo'}}, combined.cleaned_data)


    def test_initial_distributes_to_subforms(self):
        """The 'initial' kwarg of __init__ takes a nested dict."""
        class Form1(django.forms.Form):
            foo = django.forms.CharField()

        class Form2(django.forms.Form):
            foo = django.forms.CharField()

        class Formset(combinedform.CombinedForm):
            form1 = combinedform.Subform(Form1)
            form2 = combinedform.Subform(Form2)

        initial_data = {
            'form1': {'foo': 'form1 foo'},
            'form2': {'foo': 'form2 foo'},
        }

        fset = Formset(initial=initial_data)
        self.assertEqual({'foo': 'form1 foo'}, fset.form1.initial)
        self.assertEqual({'foo': 'form2 foo'}, fset.form2.initial)

    def test_non_field_errors_gets_formsets(self):
        """non_field_errors can handle formsets."""
        formset = unittest.mock.MagicMock()
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

        class MyModel(django.db.models.Model):
            a = django.db.models.CharField(max_length=10)
            b = django.db.models.CharField(max_length=10)

        class MyForm(django.forms.ModelForm):
            class Meta:
                model = MyModel
                fields = ('b',)

        MyFormSet = django.forms.formsets.formset_factory(MyForm)
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

        class Model1(django.db.models.Model):
            pass

        class Model2(django.db.models.Model):
            m1 = django.db.models.ForeignKey(Model1)

        result = combinedform.order_by_dependency([Model2, Model1])
        self.assertEqual(self.stringify(result), "1 2")

        class Model3(django.db.models.Model):
            pass

        class Model4(django.db.models.Model):
            m3 = django.db.models.ForeignKey(Model3)

        result = combinedform.order_by_dependency([Model3, Model4])
        self.assertEqual(self.stringify(result), "3 4")

    def test_second_level_fks(self):
        """Test a set of foreign key relations two levels deep."""

        """Visual of the model relationships in this test:

        m4
         \
          m2   m3
           \  /
            m1

        """
        class Model01(django.db.models.Model):
            pass

        class Model02(django.db.models.Model):
            m1 = django.db.models.ForeignKey(Model01)

        class Model03(django.db.models.Model):
            m1 = django.db.models.ForeignKey(Model01)

        class Model04(django.db.models.Model):
            m2 = django.db.models.ForeignKey(Model02)

        result = combinedform.order_by_dependency(
            [Model03, Model02, Model04, Model01])

        # there are two equivalent possibilities
        # also convert to strings because it's way easier to read the output
        result = self.stringify(result)
        self.assertIn(result, ["1 2 3 4", "1 2 4 3"])

    def test_ignores_externals(self):
        """The ordering doesn't account for models not given as arguments."""

        """Visual of the model relationships in this test:

        m1   m2
         \  /

          m3
          /
        m4

        """

        class Model001(django.db.models.Model):
            pass

        class Model002(django.db.models.Model):
            pass

        class Model003(django.db.models.Model):
            m1 = django.db.models.ForeignKey(Model001)
            m2 = django.db.models.ForeignKey(Model002)

        class Model004(django.db.models.Model):
            m3 = django.db.models.ForeignKey(Model003)

        # add extra models to artifically add depth to Model3 that's not
        # relevant for the subgraph we're interested in; test if it is properly
        # ignored
        class ModelA(django.db.models.Model):
            m3 = django.db.models.ForeignKey(Model003)

        class ModelB(django.db.models.Model):
            ma = django.db.models.ForeignKey(ModelA)

        class ModelC(django.db.models.Model):
            mb = django.db.models.ForeignKey(ModelB)

        result = combinedform.order_by_dependency(
            [Model003, Model002, Model004, Model001])
        result = self.stringify(result)
        self.assertIn(result, ["1 2 3 4", "2 1 3 4"])


class CombinedFormIntegrationTest(django.test.TestCase):
    """Test the features of CombinedForm which use the database."""

    def test_dependency_saving(self):
        """Test models are saved in a safe order and properly linked."""

        class ModelFoo(django.db.models.Model):
            description = django.db.models.CharField(max_length=20)

        class ModelBar(django.db.models.Model):
            name = django.db.models.CharField(max_length=20)
            foo = django.db.models.ForeignKey(ModelFoo)

        class ModelBuzz(django.db.models.Model):
            title = django.db.models.CharField(max_length=20)
            bar = django.db.models.ForeignKey(ModelBar)

        class FooForm(django.forms.ModelForm):
            class Meta:
                model = ModelFoo
                fields = ('description',)

        class BarForm(django.forms.ModelForm):
            class Meta:
                model = ModelBar
                fields = ('name',)

        class BuzzForm(django.forms.ModelForm):
            class Meta:
                model = ModelBuzz
                fields = ('title',)

        fset_factory = django.forms.models.inlineformset_factory
        BuzzFormset = fset_factory(ModelBar, ModelBuzz, form=BuzzForm,
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

        saved = inst.save(commit=False)  # can't do a real save on above models
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
        form = unittest.mock.MagicMock(spec=django.forms.ModelForm)
        model = unittest.mock.MagicMock(spec=django.db.models.Model)
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
