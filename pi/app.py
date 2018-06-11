###########
# imports #
###########

import json
import requests
import sseclient
from flask import Flask
from flask import jsonify, render_template, request, redirect, url_for, current_app
from flask_migrate import Migrate
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_mqtt import Mqtt
from sqlalchemy import or_, and_, desc, asc, text
from config import Config
from helpers import make_celery, save_event_from_dict

##############
# initialize #
##############

app = Flask(__name__)
app.config.from_object(Config)
mqtt = Mqtt(app)
celery = make_celery(app)
admin = Admin(app, name='p2penergy', template_mode='bootstrap3')

##################
# delayed import #
##################

from models import db, Event, EventSchema
db.init_app(app)
migrate = Migrate(app, db)

###############
# admin panel #
###############

admin.add_view(ModelView(Event, db.session))

#########
# views #
#########

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/events", methods=["GET"])
def get_events():
    query = Event.query
    query = query.order_by(desc(text("published_at")))
    items = query.all()
    if items:
        schema = EventSchema()
        result = schema.dump(items[0:5], many=True)
        return jsonify(result.data)
    else:
        return jsonify([])

########
# mqtt #
########

@mqtt.on_connect()
def handle_connect(client, userdata, flags, rc):
    mqtt.subscribe('p2penergy/photon')

@mqtt.on_message()
def handle_mqtt_message(client, userdata, message):
    data = dict(
        topic=message.topic,
        payload=message.payload.decode()
    )
    print(data)

################
# event stream #
################

@app.route("/test/event-stream")
def event_collection():
    save_particle_event_stream.delay(
        "p2p-energy-v100", app.config["PARTICLE_ACCESS_TOKEN"])
    return("Started collection.")

@celery.task()
def save_particle_event_stream(product_slug, access_token):
    url = "https://api.particle.io/v1/products/{}/events?access_token={}".format(
        product_slug, access_token)
    print(url)
    response = requests.get(url, stream=True)
    client = sseclient.SSEClient(response)
    for event in client.events():
        # event_name = event.event
        data = json.loads(event.data)
        save_event_from_dict(data)
