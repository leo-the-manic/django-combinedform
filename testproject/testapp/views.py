from django.shortcuts import render

from . import forms


def show_form(request):

    msg = ''

    if request.POST:
        form = forms.MyFormset(request.POST)
        if form.is_valid():
            msg = 'Form is valid'
    else:
        form = forms.MyFormset()

    return render(request, 'show_form.html', {'form': form, 'message': msg})
