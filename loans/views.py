from django.shortcuts import render


def hello_loans(request):
    return render(request, 'loans/hello.html')
