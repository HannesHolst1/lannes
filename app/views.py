from django.contrib.auth.decorators import login_required
from django.template import loader
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django import template
import json

## custom
from napoleon_connection import napo
from .forms import CreateRequestForm

@login_required(login_url="/login/")
def index(request):
    
    context = {}

    context['dashboards'] = napo.get_dashboards(request.user.username)
    if not context['dashboards']:
        return HttpResponseRedirect(reverse('createrequest'))

    context['segment'] = context['dashboards'][0]

    napo.load_dashboard_data(request.user.username, context['segment'], context)

    html_template = loader.get_template( 'index.html' )
    return HttpResponse(html_template.render(context, request))

@login_required(login_url="/login/")
def dashboard(request, dashboard):
    
    context = {}

    context['dashboards'] = napo.get_dashboards(request.user.username)
    if not dashboard:
        context['segment'] = context['dashboards'][0]
    else:
        if dashboard in context['dashboards']:
            context['segment'] = dashboard
        else:
            error_template = loader.get_template( 'page-500.html' )
            return HttpResponse(error_template.render({}, request))

    napo.load_dashboard_data(request.user.username, context['segment'], context)

    html_template = loader.get_template( 'index.html' )
    response = HttpResponse(html_template.render(context, request))
    response.set_cookie('last_syn', 0)
    response.set_cookie('last_score', 0)
    return response

@login_required(login_url="/login/")
def createrequest(request):
    
    context = {}
    context['segment'] = 'createrequest'

    if request.method == 'POST':
        form = CreateRequestForm(request.POST)
        if form.is_valid():
            success, status = napo.create_request(form.data, request.user.username)
            if not success:
                context['error_reason'] = status
                context['form'] = CreateRequestForm(initial=form.data)
            else:
                return HttpResponseRedirect(reverse('refresh', kwargs={'name': form.data['requestname']}))

    else:
        context['form'] = CreateRequestForm()

    html_template = loader.get_template( 'createrequest.html' )
    return HttpResponse(html_template.render(context, request))

@login_required(login_url="/login/")
def deletedashboard(request, dashboard):
    
    context = {}

    success, status = napo.delete_request(dashboard, request.user.username)
    if not success:
        context['error_reason'] = status
        HttpResponseRedirect(reverse('dashboard', kwargs={'dashboard': dashboard}))        

    return HttpResponseRedirect(reverse('home'))

@login_required(login_url="/login/")
def refresh(request, name):
    napo_response = napo.refresh_dataset(request.user.username, name)

    error_template = loader.get_template( 'page-500.html' )

    if not napo_response.ok:
        return HttpResponse(error_template.render({}, request))

    returned_json = napo_response.json()

    if not 'success' in returned_json:
        return HttpResponse(error_template.render({}, request))

    if returned_json['success'] == True:
        return HttpResponseRedirect(reverse('dashboard', kwargs={'dashboard': name}))
    else:
        return HttpResponse(error_template.render({}, request))

@login_required(login_url="/login/")
def pages(request):
    context = {}
    # All resource paths end in .html.
    # Pick out the html file name from the url. And load that template.
    try:
        
        load_template      = request.path.split('/')[-1]
        context['segment'] = load_template
        
        html_template = loader.get_template( load_template )
        return HttpResponse(html_template.render(context, request))
        
    except template.TemplateDoesNotExist:

        html_template = loader.get_template( 'page-404.html' )
        return HttpResponse(html_template.render(context, request))

    except:
    
        html_template = loader.get_template( 'page-500.html' )
        return HttpResponse(html_template.render(context, request))

@login_required(login_url="/login/")
def load_tweets(request, dashboard):
    last_syn = 0 

    if 'last_syn' in request.COOKIES:
        if request.COOKIES['last_syn'] != '0':
            last_syn = float(request.COOKIES['last_syn'])

    tweets = napo.get_tweets(dashboard, last_syn)   

    db = []
    last_syn = 0
    for i, tweet in enumerate(tweets):
        if 'tweet_html' in tweet:
            db.append(tweet['tweet_html'])
        if i == len(tweets)-1:
            last_syn = tweet['synergy']

    res = HttpResponse(json.dumps(db))
    res.set_cookie('last_syn', last_syn)

    return res

@login_required(login_url="/login/")
def load_popular_tweets(request, dashboard):
    last_score = 0 

    if 'last_score' in request.COOKIES:
        if request.COOKIES['last_score'] != '0':
            last_score = float(request.COOKIES['last_score'])

    tweets = napo.get_historic_tweets(dashboard, last_score)   

    db = []
    last_score = 0
    for i, tweet in enumerate(tweets):
        if 'tweet_html' in tweet:
            db.append(tweet['tweet_html'])
        if i == len(tweets)-1:
            last_score = tweet['tweet_score']

    res = HttpResponse(json.dumps(db))
    res.set_cookie('last_score', last_score)

    return res