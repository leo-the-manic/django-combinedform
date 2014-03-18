import django.forms

import combinedform


class MyForm1(django.forms.Form):

    fizzbuzz_field = django.forms.CharField()

    foo_field = django.forms.CharField()


class MyForm2(django.forms.Form):

    bar_field = django.forms.CharField()


class MyFormset(combinedform.CombinedForm):

    form1 = combinedform.Subform(MyForm1)

    form2 = combinedform.Subform(MyForm2)

    def validate_forms(self):

        foo_val = self.form1.cleaned_data['foo_field']
        bar_val = self.form2.cleaned_data['bar_field']

        if foo_val == 'foo' and bar_val == 'bar':
            raise combinedform.FieldValidationError(
                'form1', {'foo_field': ["Cannot be 'foo' when bar is 'bar'"]}
            )

    validators = (validate_forms,)
