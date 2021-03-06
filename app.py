# coding=utf-8
import hashlib

from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSON

from generator import train_model, combined_model, generate
import settings

MODELS = dict(andrej=train_model('andrej'), mara=train_model('caulidi'),
              andrej_korona=train_model('andrej_korona'))
MODELS['andrej1mara0'] = combined_model((MODELS['andrej'], MODELS['mara']), (3, 1))
MODELS['andrejmara'] = combined_model((MODELS['mara'], MODELS['andrej']), (1, 1))
MODELS['mara1andrej0'] = combined_model((MODELS['mara'], MODELS['andrej']), (3, 1))
MODELS = {n: m.compile(inplace=True) for n, m in MODELS.items()}

MODEL_MIXER = {1: MODELS['andrej'],
               2: MODELS['andrej1mara0'],
               3: MODELS['andrejmara'],
               4: MODELS['mara1andrej0'],
               5: MODELS['mara'],
               100: MODELS['andrej_korona'],
               }

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = settings.DB
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class Opus(db.Model):
    id = db.Column(db.String(), primary_key=True)
    conf = db.Column(JSON)
    text_long = db.Column(db.String())
    text_short = db.Column(db.String())

    def __init__(self, conf, text_long, text_short):
        self.id = hashlib.sha512((text_long+text_short).encode('utf8')).hexdigest()
        self.text_long = text_long
        self.text_short = text_short
        self.conf = conf

    @classmethod
    def hits(cls):
        return format(cls.query.count()/100000, '.5f')


@app.route('/')
def index():
    mixer = int(request.args.get('mixer', 1))
    model = MODEL_MIXER[mixer]

    tlong = generate(model, items=20, separator=' ')
    tshort = generate(model, items=12, separator='\n', max_chars=140)

    opus = Opus(conf=dict(mixer=mixer), text_long=tlong, text_short=tshort)
    db.session.add(opus)
    db.session.commit()

    return render_template('generator.html', title='Hlavně neblábolit',
                           opus=opus, hits=Opus.hits())


@app.route('/korona')
def korona():
    model = MODELS['andrej_korona']

    tlong = generate(model, items=20, separator=' ')
    tshort = generate(model, items=12, separator='\n', max_chars=140)

    opus = Opus(conf=dict(korona=True), text_long=tlong, text_short=tshort)
    db.session.add(opus)
    db.session.commit()

    return render_template('korona.html', title='Koronavirusy',
                           opus=opus, hits=Opus.hits())


@app.route('/permalink/<hash>')
def permalink(hash):
    opus = Opus.query.filter_by(id=hash).first_or_404()
    template = 'generator' if not 'korona' in opus.conf else 'korona'
    return render_template('%s.html' % template,
                           title=min(opus.text_short.split('\n'), key=len).rstrip('.'),
                           opus=opus, hits=Opus.hits())


@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html', title='Neni!'), 404


if __name__ == '__main__':
    app.run(debug=settings.DEBUG)
