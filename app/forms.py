from django import forms

class CreateRequestForm(forms.Form):
    new_request_name = forms.TextInput(attrs={'max_length': 100, 'class': "form-control", 'placeholder': "Give your request a name"})
    new_request_name = new_request_name.render('requestname', '')
    new_hashtag = forms.TextInput(attrs={'max_length': 50, 'class': "form-control", 'placeholder': "Enter the hashtag you want to monitor", 'aria-label': "Hashtag", 'aria-describedby': "basic-addon1"})
    new_hashtag = new_hashtag.render('hashtag', '')