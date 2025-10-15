# organigramma/views.py
from datetime import datetime
import json
import csv
import openpyxl

from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

from .models import Struttura, Responsabile, Qualifica
from .forms import StrutturaForm, ResponsabileForm, QualificaForm
from django.contrib.auth.decorators import login_required, permission_required
# organigramma/views.py
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import User
from django.views.generic import CreateView
from django.urls import reverse_lazy
from .forms import CreateUserForm

# views.py (import in cima)
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.db.models import Q
from django.urls import reverse_lazy
from .forms import CreateUserForm, UserUpdateForm

# Lista
class UserListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = User
    template_name = 'organigramma/user_list.html'
    context_object_name = 'users'
    paginate_by = 15
    permission_required = 'auth.view_user'
    raise_exception = False

    def get_queryset(self):
        qs = User.objects.all().order_by('username')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q))
        return qs

# Crea (aggiungo feedback)
class UserCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    form_class = CreateUserForm
    template_name = 'organigramma/user_create.html'
    success_url = reverse_lazy('user_list')
    permission_required = 'auth.add_user'
    raise_exception = False

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, f"Utente “{self.object.username}” creato correttamente.")
        return resp

# Modifica (con feedback)
class UserUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = 'organigramma/user_update.html'
    success_url = reverse_lazy('user_list')
    permission_required = 'auth.change_user'
    raise_exception = False

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, f"Utente “{self.object.username}” aggiornato correttamente.")
        return resp

# ---------------- Helpers ----------------

def _parse_on_date(request):
    """Estrae ?on=YYYY-MM-DD, default oggi."""
    on = request.GET.get("on")
    try:
        return datetime.strptime(on, "%Y-%m-%d").date() if on else timezone.now().date()
    except Exception:
        return timezone.now().date()


def _responsabile_info_attivo(responsabile, on_date):
    """Ritorna (nome, cognome, qualifica) se attivo; altrimenti ('', '', 'Vacante')."""
    if not responsabile or not responsabile.is_active(on_date):
        return "", "", "Vacante"
    qualifica = responsabile.qualifica.titolo if responsabile.qualifica else ""
    return responsabile.nome, responsabile.cognome, qualifica


# ---------------- Home / Dashboard ----------------

class PublicHomeView(TemplateView):
    template_name = "home.html"   # senza login


class PrivateHomeView(LoginRequiredMixin, TemplateView):
    template_name = "private_home.html"  # richiede login


def home(request):
    return render(request, 'home.html')


def admin_dashboard(request):
    return render(request, 'organigramma/admin_dashboard.html')


# ---------------- Organigramma (produzione) ----------------

def visualizza_organigramma(request):
    """
    Costruisce l'albero partendo dalle root (padre NULL) attive alla data.
    """
    on_date = _parse_on_date(request)

    def to_dict(s: Struttura):
        r = s.responsabile_on(on_date)  # storico
        rn = r.nome if r else ""
        rc = r.cognome if r else ""
        rq = r.qualifica.titolo if r and r.qualifica else ("Vacante" if r is None else "")
        return {
            "id": s.id,
            "codice": s.codice,
            "nome": s.nome,
            "url": s.url,
            "livello": s.livello.nome if s.livello else "",
            "livello_ordine": s.livello.ordine if s.livello else None,
            "can_be_root": s.livello.can_be_root if s.livello else False,
            "responsabile_nome": rn,
            "responsabile_cognome": rc,
            "qualifica": rq,
            "children": [to_dict(c) for c in s.active_children(on_date)],
        }

    roots_qs = (
        Struttura.objects.active_on(on_date)
        .filter(struttura_padre__isnull=True)
        .select_related("livello")
        .prefetch_related(
            "assegnazioni",
            "assegnazioni__responsabile",
            "assegnazioni__responsabile__qualifica",
            "sottostrutture",
            "sottostrutture__assegnazioni",
            "sottostrutture__assegnazioni__responsabile",
            "sottostrutture__assegnazioni__responsabile__qualifica",
        )
        .order_by("codice")
    )

    data = [to_dict(s) for s in roots_qs]

    return render(
        request,
        "organigramma/visualizza_organigramma.html",
        {"data": data, "on_date": on_date.isoformat()},
    )


# ---------------- Simulatore ----------------
# Se preferisci la CBV, lascia questa; in alternativa puoi mantenere la FBV più sotto.

class SimulatoreView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    Pagina di simulazione: richiede il permesso 'organigramma.view_simulatore'.
    Espone nel template gli stessi JSON usati nel simulatore (data_json, resp_choices_json).
    """
    template_name = "organigramma/simula_organigramma.html"
    permission_required = "organigramma.view_simulatore"
    raise_exception = False  # se non autenticato → redirect a login

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        on_date = _parse_on_date(self.request)

        def to_dict(s: Struttura):
            r = s.responsabile_on(on_date)
            return {
                "id": s.id,
                "codice": s.codice,
                "nome": s.nome,
                "url": s.url,
                "livello": s.livello.nome if s.livello else "",
                "livello_ordine": s.livello.ordine if s.livello else 99,
                "can_be_root": bool(s.livello.can_be_root) if s.livello else True,
                "responsabile_id": r.id if r else None,
                "responsabile_nome": r.nome if r else "",
                "responsabile_cognome": r.cognome if r else "",
                "qualifica": (r.qualifica.titolo if r and r.qualifica else ("Vacante" if r is None else "")),
                "children": [to_dict(c) for c in s.active_children(on_date)],
            }

        roots_qs = (
            Struttura.objects.active_on(on_date)
            .filter(struttura_padre__isnull=True)
            .select_related("livello")
            .prefetch_related(
                "assegnazioni", "assegnazioni__responsabile", "assegnazioni__responsabile__qualifica",
                "sottostrutture", "sottostrutture__livello",
                "sottostrutture__assegnazioni",
                "sottostrutture__assegnazioni__responsabile",
                "sottostrutture__assegnazioni__responsabile__qualifica",
            )
            .order_by("codice")
        )
        data = [to_dict(s) for s in roots_qs]

        resp_qs = (
            Responsabile.objects.active_on(on_date)
            .select_related("qualifica")
            .order_by("cognome", "nome")
        )
        resp_choices = [
            {
                "id": r.id,
                "label": f"{r.cognome} {r.nome}" + (f" – {r.qualifica.titolo}" if r.qualifica else "")
            }
            for r in resp_qs
        ]

        ctx.update({
            "on_date": on_date.isoformat(),
            "data_json": json.dumps(data, ensure_ascii=False),
            "resp_choices_json": json.dumps(resp_choices, ensure_ascii=False),
        })
        return ctx


# --- (Opzione) se hai ancora una URL che punta alla FBV 'simula_organigramma', la teniamo coerente:
@login_required
@permission_required('organigramma.view_simulatore', raise_exception=False)
def simula_organigramma(request):
    """Delego alla CBV per non duplicare la logica."""
    return SimulatoreView.as_view()(request)


# ---------------- API per simulatore / drag&drop (opzionale) ----------------

@login_required
def get_strutture_json(request):
    on_date = _parse_on_date(request)

    def to_dict(s):
        return {
            'id': s.id,
            'codice': s.codice,
            'nome': s.nome,
            'children': [to_dict(c) for c in s.active_children(on_date)]
        }

    roots = (
        Struttura.objects.active_on(on_date)
        .filter(struttura_padre__isnull=True)
        .order_by('codice')
    )
    return JsonResponse([to_dict(s) for s in roots], safe=False)


@csrf_exempt
@login_required
def update_struttura_padre(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        s = Struttura.objects.get(id=data.get('struttura_id'))
        s.struttura_padre_id = data.get('nuovo_padre_id')
        s.save()
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Invalid request'}, status=400)


# ---------------- Inline AJAX: crea Responsabile ----------------

@login_required
def responsabile_create_inline(request):
    """
    Crea un Responsabile dal modale (AJAX).
    Si aspetta i campi con prefix 'resp'.
    Ritorna JSON: {ok, id, label} oppure {ok:false, errors:{...}}
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'errors': {'__all__': ['Metodo non valido']}}, status=405)

    form = ResponsabileForm(request.POST, prefix='resp')
    if form.is_valid():
        obj = form.save()
        label = f"{getattr(obj, 'cognome', '')} {getattr(obj, 'nome', '')}".strip()
        if getattr(obj, 'qualifica', None):
            label = f"{label} – {obj.qualifica.titolo}"
        return JsonResponse({'ok': True, 'id': obj.pk, 'label': label})

    errors = {f: [str(e) for e in errs] for f, errs in form.errors.items()}
    return JsonResponse({'ok': False, 'errors': errors}, status=400)


# ---------------- CRUD Struttura ----------------

class StrutturaListView(LoginRequiredMixin, ListView):
    model = Struttura
    template_name = 'organigramma/struttura_list.html'
    context_object_name = 'strutture'
    paginate_by = 10

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related('livello', 'responsabile', 'responsabile__qualifica')
            .order_by('codice')
        )
        q = self.request.GET.get('q', '').strip()
        if q:
            for term in q.split():
                qs = qs.filter(
                    Q(nome__icontains=term) |
                    Q(codice__icontains=term) |
                    Q(livello__nome__icontains=term) |
                    Q(responsabile__nome__icontains=term) |
                    Q(responsabile__cognome__icontains=term)
                )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '').strip()
        return ctx


class StrutturaCreateView(LoginRequiredMixin, CreateView):
    model = Struttura
    form_class = StrutturaForm
    template_name = 'organigramma/struttura_form.html'
    success_url = reverse_lazy('struttura_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['on_date'] = _parse_on_date(self.request)
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['on_date'] = _parse_on_date(self.request)
        # form del modale inline (prefix importante!)
        ctx['resp_inline_form'] = ResponsabileForm(prefix='resp')
        return ctx

    def get_success_url(self):
        base = reverse('struttura_list')
        on = self.request.GET.get('on') or self.request.POST.get('on')
        return f"{base}?on={on}" if on else base

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Struttura salvata correttamente.")
        return resp

    def form_invalid(self, form):
        messages.error(self.request, "Controlla i campi evidenziati.")
        return super().form_invalid(form)


class StrutturaUpdateView(LoginRequiredMixin, UpdateView):
    model = Struttura
    form_class = StrutturaForm
    template_name = 'organigramma/struttura_form.html'
    success_url = reverse_lazy('struttura_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['on_date'] = _parse_on_date(self.request)
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['on_date'] = _parse_on_date(self.request)
        # form del modale inline (prefix importante!)
        ctx['resp_inline_form'] = ResponsabileForm(prefix='resp')
        return ctx

    def get_success_url(self):
        base = reverse('struttura_list')
        on = self.request.GET.get('on') or self.request.POST.get('on')
        return f"{base}?on={on}" if on else base

    def form_valid(self, form):
        resp = super().form_valid(form)
        messages.success(self.request, "Struttura aggiornata correttamente.")
        return resp

    def form_invalid(self, form):
        messages.error(self.request, "Controlla i campi evidenziati.")
        return super().form_invalid(form)


class StrutturaDeleteView(LoginRequiredMixin, DeleteView):
    model = Struttura
    template_name = 'organigramma/struttura_confirm_delete.html'
    success_url = reverse_lazy('struttura_list')


# ---------------- CRUD Responsabile ----------------

class ResponsabileListView(LoginRequiredMixin, ListView):
    model = Responsabile
    template_name = 'organigramma/responsabile_list.html'
    context_object_name = 'responsabili'
    paginate_by = 10

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related('qualifica')
            .order_by('cognome', 'nome')
        )
        q = self.request.GET.get('q', '').strip()
        if q:
            for term in q.split():
                qs = qs.filter(Q(nome__icontains=term) | Q(cognome__icontains=term))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '').strip()
        return ctx


class ResponsabileCreateView(LoginRequiredMixin, CreateView):
    model = Responsabile
    form_class = ResponsabileForm
    template_name = 'organigramma/responsabile_form.html'
    success_url = reverse_lazy('responsabile_list')


class ResponsabileUpdateView(LoginRequiredMixin, UpdateView):
    model = Responsabile
    form_class = ResponsabileForm
    template_name = 'organigramma/responsabile_form.html'
    success_url = reverse_lazy('responsabile_list')


class ResponsabileDeleteView(LoginRequiredMixin, DeleteView):
    model = Responsabile
    template_name = 'organigramma/responsabile_confirm_delete.html'
    success_url = reverse_lazy('responsabile_list')


# ---------------- CRUD Qualifica ----------------

class QualificaListView(LoginRequiredMixin, ListView):
    model = Qualifica
    template_name = 'organigramma/qualifica_list.html'
    context_object_name = 'qualifiche'


class QualificaCreateView(LoginRequiredMixin, CreateView):
    model = Qualifica
    form_class = QualificaForm
    template_name = 'organigramma/qualifica_form.html'
    success_url = reverse_lazy('qualifica_list')


class QualificaUpdateView(LoginRequiredMixin, UpdateView):
    model = Qualifica
    form_class = QualificaForm
    template_name = 'organigramma/qualifica_form.html'
    success_url = reverse_lazy('qualifica_list')


class QualificaDeleteView(LoginRequiredMixin, DeleteView):
    model = Qualifica
    template_name = 'organigramma/qualifica_confirm_delete.html'
    success_url = reverse_lazy('qualifica_list')



# ---------------- Export CSV / Excel ----------------

@login_required
def export_csv(request):
    on_date = _parse_on_date(request)
    qs = (
        Struttura.objects.active_on(on_date)
        .select_related('livello')
        .prefetch_related('assegnazioni', 'assegnazioni__responsabile', 'assegnazioni__responsabile__qualifica')
        .order_by('codice')
    )

    response = HttpResponse(content_type='text/csv')
    filename = f'strutture_{on_date.isoformat()}.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow([
        'Codice', 'Nome', 'Livello', 'Data Inizio', 'Data Fine',
        'Resp. Nome', 'Resp. Cognome', 'Qualifica/Note'
    ])
    for s in qs:
        r = s.responsabile_on(on_date)
        rn = r.nome if r else ''
        rc = r.cognome if r else ''
        rq = r.qualifica.titolo if r and r.qualifica else ('Vacante' if r is None else '')
        writer.writerow([
            s.codice, s.nome, s.livello.nome if s.livello else '',
            s.data_inizio, s.data_fine, rn, rc, rq
        ])
    return response


@login_required
def export_excel(request):
    on_date = _parse_on_date(request)
    qs = (
        Struttura.objects.active_on(on_date)
        .select_related('livello')
        .prefetch_related('assegnazioni', 'assegnazioni__responsabile', 'assegnazioni__responsabile__qualifica')
        .order_by('codice')
    )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Strutture_{on_date.isoformat()}"
    ws.append([
        'Codice', 'Nome', 'Livello', 'Data Inizio', 'Data Fine',
        'Resp. Nome', 'Resp. Cognome', 'Qualifica/Note'
    ])

    for s in qs:
        r = s.responsabile_on(on_date)
        rn = r.nome if r else ''
        rc = r.cognome if r else ''
        rq = r.qualifica.titolo if r and r.qualifica else ('Vacante' if r is None else '')
        ws.append([
            s.codice, s.nome, s.livello.nome if s.livello else '',
            s.data_inizio, s.data_fine, rn, rc, rq
        ])

    resp = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = f'strutture_{on_date.isoformat()}.xlsx'
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(resp)
    return resp
