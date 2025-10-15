from datetime import timedelta, date
from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.utils import timezone


# =========================
# Qualifica
# =========================

class Qualifica(models.Model):
    titolo = models.CharField(max_length=100, null=False)
    dirigente = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Qualifica"
        verbose_name_plural = "Qualifiche"

    def __str__(self):
        return f"{self.titolo}"


# =========================
# Livello
# =========================

class Livello(models.Model):
    nome = models.CharField(max_length=50)
    descrizione = models.TextField(null=True, blank=True)
    ordine = models.PositiveIntegerField(
        default=0,
        help_text="0 = livello più alto (es. Ente=0, Direzione=1, Ripartizione=2, Settore=3, POEQ=4)"
    )
    can_be_root = models.BooleanField(
        default=True,
        help_text="Se disattivato, le strutture di questo livello DEVONO avere un padre."
    )
    # Mappa esplicita dei livelli ammessi come padre di questo livello
    allowed_parents = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='allowed_children',
        help_text=(
            "Se valorizzato, il padre DEVE appartenere a uno di questi livelli. "
            "Se vuoto, si applica la regola d'ordine (padre.ordine < figlio.ordine)."
        )
    )

    class Meta:
        verbose_name = "Livello"
        verbose_name_plural = "Livelli"
        ordering = ["ordine", "nome"]

    def __str__(self):
        return self.nome


# =========================
# Responsabile
# =========================

class ResponsabileQuerySet(models.QuerySet):
    def active_on(self, on_date):
        return self.filter(
            Q(data_inizio__isnull=True) | Q(data_inizio__lte=on_date),
            Q(data_fine__isnull=True)   | Q(data_fine__gte=on_date)
        )


class Responsabile(models.Model):
    nome = models.CharField(max_length=100)
    cognome = models.CharField(max_length=100)
    codice_fiscale = models.CharField(max_length=16, null=True, blank=True)
    email = models.EmailField(max_length=254, null=True, blank=True)
    qualifica = models.ForeignKey(Qualifica, on_delete=models.SET_NULL, null=True, related_name="responsabili")
    in_carica = models.BooleanField(default=True)
    data_inizio = models.DateField(default=timezone.now)
    data_fine = models.DateField(null=True, blank=True)

    objects = models.Manager.from_queryset(ResponsabileQuerySet)()

    class Meta:
        verbose_name = "Responsabile"
        verbose_name_plural = "Responsabili"

    def __str__(self):
        q = f" - {self.qualifica.titolo}" if getattr(self, "qualifica", None) else ""
        return f"{self.nome} {self.cognome}{q}"

    def is_active(self, d=None):
        d = d or timezone.now().date()
        return ((self.data_inizio is None or self.data_inizio <= d) and
                (self.data_fine   is None or self.data_fine   >= d))

    def clean(self):
        if self.data_inizio and self.data_fine and self.data_fine < self.data_inizio:
            raise ValidationError({"data_fine": "La data di fine non può precedere la data di inizio."})


# =========================
# Struttura
# =========================

class StrutturaQuerySet(models.QuerySet):
    def active_on(self, on_date):
        return self.filter(
            Q(data_inizio__isnull=True) | Q(data_inizio__lte=on_date),
            Q(data_fine__isnull=True)   | Q(data_fine__gte=on_date)
        )


class Struttura(models.Model):
    nome = models.CharField(max_length=100)
    livello = models.ForeignKey(Livello, on_delete=models.CASCADE, related_name="strutture")

    # FK "non storico" (fallback/UI veloce). Lo storico vero è nel through StrutturaResponsabile.
    responsabile = models.ForeignKey(
        'Responsabile', on_delete=models.SET_NULL, null=True, blank=True, related_name="strutture",
        help_text="Campo non storico: mantenuto per retro-compatibilità. Per lo storico usa le 'Assegnazioni'."
    )

    struttura_padre = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name="sottostrutture"
    )
    codice = models.CharField(max_length=50, editable=False, null=True)
    data_inizio = models.DateField(default=timezone.now)
    data_fine = models.DateField(null=True, blank=True)
    historical_parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name="former_children"
    )
    num_ode = models.PositiveIntegerField(null=True, blank=True, unique=True)
    num_eng = models.PositiveIntegerField(null=True, blank=True, unique=True)
    url = models.URLField(max_length=200, null=True, blank=True)

    # Storico responsabili
    responsabili_storici = models.ManyToManyField(
        'Responsabile',
        through='StrutturaResponsabile',
        related_name='strutture_storiche',
        blank=True
    )

    objects = models.Manager.from_queryset(StrutturaQuerySet)()

    class Meta:
        verbose_name = "Struttura"
        verbose_name_plural = "Strutture"
        ordering = ["codice"]
        indexes = [
            models.Index(fields=['struttura_padre']),
            models.Index(fields=['data_inizio', 'data_fine']),
        ]

    def __str__(self):
        # Evita eccezioni se il livello non è impostato o è stato cancellato
        lvl_name = ""
        try:
            if self.livello_id:
                lvl_name = self.livello.nome
        except Exception:
            lvl_name = ""
        return f"{self.nome} - Livello {lvl_name}" if lvl_name else self.nome

    # ---- Stato attività

    def is_active(self, d=None):
        d = d or timezone.now().date()
        return ((self.data_inizio is None or self.data_inizio <= d) and
                (self.data_fine   is None or self.data_fine   >= d))

    def active_children(self, on_date):
        return self.sottostrutture.active_on(on_date).order_by('codice')

    @property
    def has_children(self):
        return self.sottostrutture.exists()

    # --- VALIDAZIONE GERARCHIA ---
    def clean(self):
        super().clean()

        # 1) periodo coerente
        if self.data_inizio and self.data_fine and self.data_fine < self.data_inizio:
            raise ValidationError({"data_fine": "La data di fine non può precedere la data di inizio."})

        # 2) no self-parent / no cicli
        if self.struttura_padre_id:
            if self.pk and self.struttura_padre_id == self.pk:
                raise ValidationError({"struttura_padre": "Una struttura non può essere padre di sé stessa."})
            ancestor = self.struttura_padre
            while ancestor is not None:
                if self.pk and ancestor.pk == self.pk:
                    raise ValidationError({"struttura_padre": "Ciclo gerarchico non consentito."})
                ancestor = ancestor.struttura_padre

        # Carica (in modo sicuro) il livello della struttura e del padre
        lvl = None
        if self.livello_id:
            # uso filter().only() per evitare eccezioni del descriptor e ridurre query
            lvl = Livello.objects.filter(pk=self.livello_id).only('id', 'nome', 'ordine', 'can_be_root').first()

        padre = self.struttura_padre
        padre_lvl = None
        if padre and padre.livello_id:
            padre_lvl = Livello.objects.filter(pk=padre.livello_id).only('id', 'nome', 'ordine').first()

        # 3) regola root
        if self.struttura_padre is None:
            # Se il livello esiste e NON può essere root → errore
            if lvl and not lvl.can_be_root:
                raise ValidationError({"struttura_padre": "Questo livello non può stare alla radice. Seleziona un padre."})
            # Se il livello non è valorizzato, non aggiungo altri vincoli qui: sarà il form a richiederlo.
            return  # niente altro da verificare per i root ammessi

        # 4) regola parent-child per livelli (se entrambi presenti)
        if not lvl or not padre_lvl:
            return

        # 4a) whitelist dei livelli padre (se configurata)
        if Livello.allowed_parents.rel.through.objects.filter(from_livello_id=lvl.id).exists():
            # Nota: per evitare join pesanti, verifichiamo la M2M via through
            ok = Livello.allowed_parents.rel.through.objects.filter(
                from_livello_id=lvl.id,
                to_livello_id=padre_lvl.id
            ).exists()
            if not ok:
                raise ValidationError({
                    "struttura_padre": f"Il livello del padre '{padre_lvl.nome}' non è consentito per '{lvl.nome}'.",
                    "livello": "Seleziona un livello coerente con la gerarchia configurata."
                })
        else:
            # 4b) fallback: ordine gerarchico (padre più alto)
            if padre_lvl.ordine >= lvl.ordine:
                raise ValidationError({
                    "livello": "Il livello del figlio deve avere ordine maggiore (più basso in gerarchia) del padre.",
                    "struttura_padre": "Seleziona un padre con livello più alto (ordine minore)."
                })

    # ---- Numerazione gerarchica (codice)

    def _generate_code_for_parent(self, parent):
        """Genera il prossimo codice disponibile sotto il padre dato."""
        parent_code = parent.codice
        siblings = Struttura.objects.filter(struttura_padre=parent).exclude(pk=self.pk).order_by('codice')
        if siblings.exists():
            last_code = (siblings.last().codice or "").split('.')
            try:
                new_suffix = int(last_code[-1]) + 1
            except Exception:
                new_suffix = 1
            return f"{parent_code}.{new_suffix}"
        return f"{parent_code}.1"

    def _generate_code_for_root(self):
        """Genera il prossimo codice root disponibile."""
        siblings = Struttura.objects.filter(struttura_padre=None).exclude(pk=self.pk).order_by('codice')
        if siblings.exists():
            try:
                return str(int(siblings.last().codice) + 1)
            except (TypeError, ValueError):
                return "1"
        return "1"

    # ---- Storico assegnazioni: utilità

    def current_assignment(self, d=None):
        """Ritorna l'assegnazione attiva alla data (default: oggi)."""
        d = d or timezone.now().date()
        return (self.assegnazioni
                    .active_on(d)
                    .select_related('responsabile', 'responsabile__qualifica')
                    .order_by('-data_inizio')
                    .first())

    def sync_assignment_from_fk(self, effective_date=None):
        """
        Sincronizza lo STORICO con il valore corrente del FK self.responsabile.
        - Chiude l’assegnazione corrente (se diversa) al giorno precedente.
        - Crea una nuova assegnazione dal giorno 'effective_date' (default: oggi).
        - Se il FK è None, chiude solo l’assegnazione corrente.
        """
        d = effective_date or timezone.now().date()
        new_resp = self.responsabile  # può essere None
        cur = self.current_assignment(d)

        # Se uguale all'attuale, nulla da fare
        if cur and new_resp and cur.responsabile_id == new_resp.id:
            return

        # Chiudi l’assegnazione corrente (se c’è)
        if cur:
            end = d - timedelta(days=1)
            if cur.data_inizio and end < cur.data_inizio:
                end = cur.data_inizio  # evita fine < inizio
            if cur.data_fine is None or cur.data_fine != end:
                cur.data_fine = end
                cur.full_clean()
                cur.save()

        # Se c'è un nuovo responsabile, apri una nuova riga storica
        if new_resp:
            start = max(d, self.data_inizio or d)
            StrutturaResponsabile.objects.create(
                struttura=self,
                responsabile=new_resp,
                data_inizio=start
            )

    # ---- Storico assegnazioni: responsabile "alla data"

    def responsabile_on(self, on_date):
        """
        Ritorna il Responsabile assegnato a questa struttura alla data on_date.
        1) Cerca in StrutturaResponsabile (storico).
        2) In fallback usa il FK self.responsabile se attivo a quella data.
        """
        assegn = (self.assegnazioni
                    .active_on(on_date)
                    .select_related('responsabile', 'responsabile__qualifica')
                    .order_by('-data_inizio')
                    .first())
        if assegn:
            r = assegn.responsabile
            if r and r.is_active(on_date):
                return r

        r_fk = self.responsabile
        if r_fk and r_fk.is_active(on_date):
            return r_fk

        return None

    def save(self, *args, **kwargs):
        # Capire se il padre o il responsabile sono cambiati
        parent_changed = False
        resp_changed = False
        old_parent_id = None
        prev_resp_id = None

        was_adding = self._state.adding  # True se è una nuova istanza

        if self.pk:
            try:
                old = Struttura.objects.get(pk=self.pk)
                old_parent_id = old.struttura_padre_id
                prev_resp_id = old.responsabile_id
            except Struttura.DoesNotExist:
                old_parent_id = None
                prev_resp_id = None

        new_parent_id = self.struttura_padre_id
        parent_changed = (old_parent_id != new_parent_id)
        resp_changed = (prev_resp_id != self.responsabile_id)

        # Calcola/ricalcola il codice SOLO se manca o cambia il padre
        if not self.codice or parent_changed:
            if self.struttura_padre:
                self.codice = self._generate_code_for_parent(self.struttura_padre)
            else:
                self.codice = self._generate_code_for_root()

        # Salva la struttura (serve l'ID per creare assegnazioni)
        super().save(*args, **kwargs)

        # Sincronizza lo storico se nuova struttura con FK o se il FK è cambiato
        if was_adding or resp_changed:
            self.sync_assignment_from_fk(effective_date=timezone.now().date())


# =========================
# Assegnazione Responsabile ↔ Struttura (storico)
# =========================

class StrutturaResponsabileQuerySet(models.QuerySet):
    def active_on(self, on_date):
        return self.filter(
            Q(data_inizio__isnull=True) | Q(data_inizio__lte=on_date),
            Q(data_fine__isnull=True)   | Q(data_fine__gte=on_date),
        )


class StrutturaResponsabile(models.Model):
    struttura = models.ForeignKey('Struttura', on_delete=models.CASCADE, related_name='assegnazioni')
    responsabile = models.ForeignKey('Responsabile', on_delete=models.CASCADE, related_name='assegnazioni')
    data_inizio = models.DateField(default=timezone.now)
    data_fine   = models.DateField(null=True, blank=True)

    objects = models.Manager.from_queryset(StrutturaResponsabileQuerySet)()

    class Meta:
        verbose_name = "Assegnazione responsabile"
        verbose_name_plural = "Assegnazioni responsabili"
        ordering = ['struttura', 'data_inizio']
        indexes = [
            models.Index(fields=['struttura', 'data_inizio', 'data_fine']),
            models.Index(fields=['responsabile', 'data_inizio', 'data_fine']),
        ]

    def __str__(self):
        fino = self.data_fine or '…'
        return f"{self.struttura} ← {self.responsabile} [{self.data_inizio} – {fino}]"

    def is_active(self, d=None):
        d = d or timezone.now().date()
        return ((self.data_inizio is None or self.data_inizio <= d) and
                (self.data_fine   is None or self.data_fine   >= d))

    def clean(self):
        # Coerenza date
        if self.data_inizio and self.data_fine and self.data_fine < self.data_inizio:
            raise ValidationError({"data_fine": "La data di fine non può precedere la data di inizio."})

        # Se la struttura non è ancora stata assegnata al record, evita controlli d'overlap
        if not getattr(self, 'struttura_id', None):
            return

        a0 = self.data_inizio
        a1 = self.data_fine or date(9999, 12, 31)  # "infinito"

        # no sovrapposizioni per la stessa struttura
        qs = StrutturaResponsabile.objects.filter(struttura=self.struttura).exclude(pk=self.pk)
        overlap = qs.filter(
            Q(data_inizio__lte=a1) &
            (Q(data_fine__isnull=True) | Q(data_fine__gte=a0))
        ).exists()
        if overlap:
            raise ValidationError("Esiste già un'assegnazione sovrapposta per questa struttura.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
