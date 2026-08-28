"""
URL configuration for helloworld_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from accounts import views as accounts_views
from ham.ham import views
from loans import views as loans_views
from payments import views as payments_views
from ledger import views as ledger_views
from rules import views as rules_views
from dashboard import views as dashboard_views
from expenses import views as expenses_views
from fd import views as fd_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', accounts_views.login_view, name='login'),
    path('logout/', accounts_views.logout_view, name='logout'),
    path('', views.hello_world, name='hello_world'),
    path('loans/', loans_views.hello_loans, name='hello_loans'),
    path('payments/', payments_views.hello_payments, name='hello_payments'),
    path('payments/send/', payments_views.send_payment, name='send_payment'),
    path('payments/approve/', payments_views.approve_payments, name='approve_payments'),
    path('ledger/', ledger_views.hello_ledger, name='hello_ledger'),
    path('rules/', rules_views.hello_rules, name='hello_rules'),
    path('dashboard/', dashboard_views.hello_dashboard, name='hello_dashboard'),
    path('expenses/', expenses_views.hello_expenses, name='hello_expenses'),
    path('expenses/add/', expenses_views.add_transaction, name='add_transaction'),
    path('fd/', fd_views.hello_fd, name='hello_fd'),
    path('fd/create/', fd_views.create_fd, name='create_fd'),
    path('fd/<int:fd_id>/complete/', fd_views.complete_fd, name='complete_fd'),
]
