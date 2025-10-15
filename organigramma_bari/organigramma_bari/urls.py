from django.contrib import admin
from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import TemplateView

from organigramma.views import (
    PublicHomeView, PrivateHomeView,              # home pubblica/privata
    admin_dashboard,
    visualizza_organigramma, export_csv, export_excel,
    StrutturaListView, StrutturaCreateView, StrutturaUpdateView, StrutturaDeleteView,
    ResponsabileListView, ResponsabileCreateView, ResponsabileUpdateView, ResponsabileDeleteView,
    QualificaListView, QualificaCreateView, QualificaUpdateView, QualificaDeleteView,
    UserCreateView, UserListView, UserUpdateView,
    get_strutture_json, update_struttura_padre,
    simula_organigramma,
    responsabile_create_inline,                  # <-- AGGIUNTO
)

from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    # Home
    path('', PublicHomeView.as_view(), name='home'),                 # pubblica (no login)
    path('dashboard/', PrivateHomeView.as_view(), name='private_home'),  # privata (login)

    # Auth
    path('login/', LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', LogoutView.as_view(next_page='home'), name='logout'),

    # Admin Django
    path('admin/', admin.site.urls),

    # Dashboard interna opzionale
    path('admin_dashboard/', admin_dashboard, name='admin_dashboard'),

    # Utenti
    path('utenti/', UserListView.as_view(), name='user_list'),
    path('utenti/nuovo/', UserCreateView.as_view(), name='user_create'),
    path('utenti/modifica/<int:pk>/', UserUpdateView.as_view(), name='user_update'),

    # Organigramma (produzione)
    path('visualizza_organigramma/', visualizza_organigramma, name='visualizza_organigramma'),
    path('export_csv/', export_csv, name='export_csv'),
    path('export_excel/', export_excel, name='export_excel'),

    # Strutture
    path('strutture/', StrutturaListView.as_view(), name='struttura_list'),
    path('strutture/nuovo/', StrutturaCreateView.as_view(), name='struttura_create'),
    path('strutture/modifica/<int:pk>/', StrutturaUpdateView.as_view(), name='struttura_update'),
    path('strutture/elimina/<int:pk>/', StrutturaDeleteView.as_view(), name='struttura_delete'),

    # Responsabili
    path('responsabili/', ResponsabileListView.as_view(), name='responsabile_list'),
    path('responsabili/nuovo/', ResponsabileCreateView.as_view(), name='responsabile_create'),
    path('responsabili/modifica/<int:pk>/', ResponsabileUpdateView.as_view(), name='responsabile_update'),
    path('responsabili/elimina/<int:pk>/', ResponsabileDeleteView.as_view(), name='responsabile_delete'),

    # Qualifiche
    path('qualifiche/', QualificaListView.as_view(), name='qualifica_list'),
    path('qualifiche/nuovo/', QualificaCreateView.as_view(), name='qualifica_create'),
    path('qualifiche/modifica/<int:pk>/', QualificaUpdateView.as_view(), name='qualifica_update'),
    path('qualifiche/elimina/<int:pk>/', QualificaDeleteView.as_view(), name='qualifica_delete'),

    # Editor Drag&Drop
    path('editor/', TemplateView.as_view(template_name="organigramma/editor_dragdrop.html"), name='editor_organigramma'),

    # API per editor
    path('api/strutture/', get_strutture_json, name='get_strutture_json'),
    path('api/update_padre/', update_struttura_padre, name='update_padre'),

    # Simulatore (protetto da permesso nella view)
    path('simulatore/', simula_organigramma, name='simula_organigramma'),

    # AJAX inline: crea Responsabile (POST -> JSON)
    path('ajax/responsabili/nuovo/', responsabile_create_inline, name='responsabile_create_inline'),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
