from django.contrib.auth.forms import UserCreationForm, SetPasswordForm
from django.contrib.auth import get_user_model
from django import forms
from .models import CustomUser

class CustomUserCreationForm(UserCreationForm):
    username = forms.CharField(
        max_length=150,
        required=True,
        help_text='Обязательное поле. 150 символов или меньше. Только буквы, цифры и @/./+/-/_ .'
    )
    email = forms.EmailField(required=True)
    full_name = forms.CharField(max_length=255, required=True)
    role = forms.ChoiceField(choices=CustomUser.ROLE_CHOICES)
    is_active = forms.BooleanField(required=False, initial=True)

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'full_name', 'role', 'is_active', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['username']
        user.email = self.cleaned_data['email']
        user.full_name = self.cleaned_data['full_name']
        user.role = self.cleaned_data['role']
        user.is_active = self.cleaned_data['is_active']
        if commit:
            user.save()
        return user

class CustomUserUpdateForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Новый пароль',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        help_text='Оставьте пустым, если не хотите менять пароль'
    )
    password2 = forms.CharField(
        label='Подтверждение пароля',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        help_text='Введите тот же пароль, что и выше'
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'full_name', 'role', 'is_active')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Пароли не совпадают')
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password1')
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user 