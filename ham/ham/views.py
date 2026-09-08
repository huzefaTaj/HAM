from django.shortcuts import redirect


def hello_world(request):
    if request.user.is_authenticated:
        return redirect('hello_dashboard')
    return redirect('login')
