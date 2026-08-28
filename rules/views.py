from django.shortcuts import render

from core.constants import ANNUAL_DUE, MONTHLY_DUE, MONTHLY_FINE


def hello_rules(request):
    return render(request, 'rules/hello.html', {
        'annual_due': ANNUAL_DUE,
        'monthly_due': MONTHLY_DUE,
        'monthly_fine': MONTHLY_FINE,
    })
