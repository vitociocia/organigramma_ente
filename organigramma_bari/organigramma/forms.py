from django import forms
from django.utils import timezone
from .models import Struttura, Responsabile, Qualifica


# ---------------------------
# Utility
# ---------------------------

def _active_qs(qs, on_date):
    """
    Se il Manager del modello espone active_on(on_date) applica il filtro;
    altrimenti restituisce il queryset così com'è.
    """
    if hasattr(qs.model.objects, 'active_on'):
        return qs.model.objects.active_on(on_date)
    return qs


class ErrorStylingMixin:
    """
    Aggiunge automaticamente la classe Bootstrap 'is-invalid' ai campi con errori.
    Lo facciamo dopo la validazione sovrascrivendo full_clean().
    """
    def _apply_error_classes(self):
        for name, field in self.fields.items():
            widget = field.widget
            css = widget.attrs.get("class", "")
            if name in self.errors:
                if "is-invalid" not in css:
                    widget.attrs["class"] = (css + " is-invalid").strip()
                widget.attrs["aria-invalid"] = "true"
            else:
                widget.attrs.pop("aria-invalid", None)

    def full_clean(self):
        super().full_clean()
        # a questo punto self.errors è valorizzato
        self._apply_error_classes()


# ---------------------------
# Modulo per Struttura
# ---------------------------

class StrutturaForm(ErrorStylingMixin, forms.ModelForm):
    """
    Le scelte di 'responsabile' e 'struttura_padre' sono filtrate agli elementi
    attivi alla data 'on_date' (passata dalla view; default: oggi).
    """
    class Meta:
        model = Struttura
        fields = [
            'nome', 'livello', 'responsabile', 'struttura_padre',
            'data_inizio', 'data_fine',
            'num_ode', 'num_eng', 'url'
        ]
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Inserisci il nome della struttura'
            }),
            'livello': forms.Select(attrs={'class': 'form-control'}),
            'responsabile': forms.Select(attrs={'class': 'form-control'}),
            'struttura_padre': forms.Select(attrs={'class': 'form-control'}),
            'data_inizio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'data_fine': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'num_ode': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'num_eng': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
        }
        help_texts = {
            'responsabile': 'Mostra solo responsabili attivi alla data selezionata.',
            'struttura_padre': 'Mostra solo strutture attive alla data selezionata.',
            'data_inizio': 'Predefinito: oggi (se non indicato).',
            'data_fine': 'Compila solo in caso di cessazione; deve essere ≥ data inizio.',
        }

    def __init__(self, *args, **kwargs):
        # data di riferimento per filtrare le scelte (passata dalla view)
        self.on_date = kwargs.pop('on_date', None) or timezone.now().date()
        super().__init__(*args, **kwargs)

        # Filtra scelte in base all'attività
        self.fields['responsabile'].queryset = _active_qs(
            Responsabile.objects.all(), self.on_date
        ).order_by('cognome', 'nome')

        padre_qs = _active_qs(Struttura.objects.all(), self.on_date)
        # Esclude se stessa dall'elenco padri (utile in update)
        if self.instance and self.instance.pk:
            padre_qs = padre_qs.exclude(pk=self.instance.pk)
        self.fields['struttura_padre'].queryset = padre_qs.order_by('codice')

        # Default comodo in creazione
        if not self.instance.pk and not self.initial.get('data_inizio'):
            self.initial['data_inizio'] = timezone.now().date()

    def clean(self):
        cleaned = super().clean()
        di = cleaned.get('data_inizio')
        df = cleaned.get('data_fine')
        if di and df and df < di:
            self.add_error('data_fine', 'La data di fine non può essere precedente alla data di inizio.')
        return cleaned


# ---------------------------
# Modulo per Responsabile
# ---------------------------

class ResponsabileForm(ErrorStylingMixin, forms.ModelForm):
    class Meta:
        model = Responsabile
        fields = [
            'nome', 'cognome', 'codice_fiscale', 'email',
            'qualifica', 'in_carica', 'data_inizio', 'data_fine'
        ]
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Inserisci il nome'}),
            'cognome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Inserisci il cognome'}),
            'codice_fiscale': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Inserisci il codice fiscale'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': "Inserisci l'email"}),
            'qualifica': forms.Select(attrs={'class': 'form-control'}),
            'in_carica': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'data_inizio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'data_fine': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
        help_texts = {
            'data_inizio': 'Predefinito: oggi (se non indicato).',
            'data_fine': 'Compila solo in caso di cessazione; deve essere ≥ data inizio.',
        }

    def clean(self):
        cleaned = super().clean()
        di = cleaned.get('data_inizio')
        df = cleaned.get('data_fine')
        if di and df and df < di:
            self.add_error('data_fine', 'La data di fine non può essere precedente alla data di inizio.')
        return cleaned


# ---------------------------
# Modulo per Qualifica
# ---------------------------

class QualificaForm(ErrorStylingMixin, forms.ModelForm):
    class Meta:
        model = Qualifica
        fields = ['titolo', 'dirigente']
        widgets = {
            'titolo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Inserisci il titolo della qualifica'
            }),
            'dirigente': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
# Aggiungere utenti (aggiungi)
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User, Group

class CreateUserForm(UserCreationForm):
    email = forms.EmailField(required=False)
    gruppo = forms.ModelChoiceField(
        queryset=Group.objects.filter(name__in=['Base','Avanzati','Amministratori']),
        required=True, empty_label=None, label="Ruolo"
    )
    is_superuser = forms.BooleanField(required=False, label="Amministratore (superuser)")

    class Meta:
        model = User
        fields = ('username','email','password1','password2','gruppo','is_superuser')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get('email','')
        user.is_staff = True  # opzionale: lo abilita a entrare in /admin se vuoi
        user.is_superuser = bool(self.cleaned_data.get('is_superuser'))
        if commit:
            user.save()
            # assegna gruppo
            g = self.cleaned_data['gruppo']
            user.groups.clear()
            user.groups.add(g)
        return user
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['email'].widget.attrs.update({'class': 'form-control'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})
        self.fields['gruppo'].widget.attrs.update({'class': 'form-select'})
        self.fields['is_superuser'].widget.attrs.update({'class': 'form-check-input'})

from django import forms
from django.contrib.auth.models import User, Group

class UserUpdateForm(forms.ModelForm):
    gruppo = forms.ModelChoiceField(
        queryset=Group.objects.filter(name__in=['Base','Avanzati','Amministratori']),
        required=True, empty_label=None, label="Ruolo"
    )
    is_superuser = forms.BooleanField(required=False, label="Amministratore (superuser)")
    is_active = forms.BooleanField(required=False, label="Attivo")

    class Meta:
        model = User
        fields = ('username', 'email', 'is_active', 'gruppo', 'is_superuser')
        widgets = {'username': forms.TextInput(attrs={'readonly': 'readonly'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ['username', 'email']:
            self.fields[f].widget.attrs.update({'class': 'form-control'})
        self.fields['gruppo'].widget.attrs.update({'class': 'form-select'})
        self.fields['is_superuser'].widget.attrs.update({'class': 'form-check-input'})
        self.fields['is_active'].widget.attrs.update({'class': 'form-check-input'})

        if self.instance and self.instance.pk:
            g = self.instance.groups.filter(name__in=['Base','Avanzati','Amministratori']).first()
            if g:
                self.initial['gruppo'] = g.pk

    def save(self, commit=True):
        user = super().save(commit=commit)
        g = self.cleaned_data['gruppo']
        user.groups.clear()
        user.groups.add(g)
        return user
