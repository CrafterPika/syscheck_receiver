# modules
import flask
import json
import os
import string
import random
import sqlite3
import time
import html
import zipfile
from argparse import ArgumentParser
from flask import Flask, request, render_template, send_file
from datetime import datetime
from io import BytesIO

# stuff
with open(f"{os.getcwd()}/config.json", "r") as f:
    config = json.load(f)

parser = ArgumentParser()
parser.add_argument("-d", "--debug", dest="debug")
args = parser.parse_args()

def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

def get_console_id(txt):
    array = txt.split("\n")
    for ln in array:
        if ln.startswith("Console ID: "):
            return ln.split(":")[1][1:]

    return "0"

# docker
if config["docker"]:
    report_dir = "/data/reports"
    db_dir = "/data/reports.db"
else:
    report_dir = f"{os.getcwd()}/reports"
    db_dir = f"{os.getcwd()}/reports.db"

# sever code
app = Flask('syscheck_receiver')

@app.route("/")
def index():
    # Get data
    db = sqlite3.connect(db_dir)
    cursor = db.cursor()
    uploads = cursor.execute("SELECT * FROM reports ORDER BY ROWID DESC LIMIT 15").fetchall()
    report_count = cursor.execute("SELECT COUNT(*) FROM reports").fetchall()
    db.close()

    # Make HTML Page
    uploadIndex=""
    for upload in uploads:
        upload_time = datetime.fromtimestamp(upload[1])
        uploadIndex+="ID: <a href='/view_report?id={}' target='_blank'>{}</a> --  Uploaded at {}!<br>".format(upload[0], upload[0], upload_time)

    return render_template("index.html", uploadIndex=uploadIndex, report_count=report_count[0][0]), 200

@app.route("/syscheck_send.php", methods=["POST"]) # SysCheck2.1.0b.19
@app.route("/syscheck_receiver.php", methods=["POST"]) # literally anything else
def syscheck_report():
    form_data = request.form.to_dict(flat=False)
    report_txt = form_data["syscheck"][0]
    console_id = get_console_id(report_txt)
    if console_id == "0":
        return "ERROR: Not a valid sysCheck!", 200
    console_id_censor = "Console ID: "+console_id[:-4]+"***"
    timestamp = int(time.time())
    report_id = id_generator(6, 'AaBbCcDdFfeEgGhHiIjJkKlLmMnNoOpPqQrRsStTuUvVwWXxYyZz1234567890')

    if form_data["password"][0] in config["upload_passwords"]:
        try:
            with open(f"{report_dir}/{report_id}.csv", "a+") as report:
                report.write(report_txt.replace(f"Console ID: {console_id}", "Console ID: {}".format(console_id_censor)))

            db = sqlite3.connect(db_dir)
            cursor = db.cursor()
            cursor.execute("INSERT INTO reports VALUES ('{}', {}, {})".format(report_id, timestamp, console_id))
            db.commit()
            db.close()

            return f"Success! Report ID: {report_id}", 200
        except:
            return "ERROR: Failed to save SysCheck report!", 200
        
    else:
        return "ERROR: Unauthorized", 200

@app.route("/view_report", methods=["GET"])
def view_report():
    report_id = request.args.get("id")
    if os.path.isfile(f"{report_dir}/{report_id}.csv"):
        with open(f"{report_dir}/{report_id}.csv", "r") as report:
            return render_template("view_report.html", report_id=report_id, report_content=html.escape(report.read())), 200
    else:
        return "Report does not exist.", 404

@app.route("/syscheck2", methods=["GET"])
def syscheck():
    if len("http://syscheck.softwii.de/syscheck_receiver.php") < len(config["replace_str"]):
        return "Replacement host has to be exactly 48 characters; Specified URL is too long!", 400
    elif len("http://syscheck.softwii.de/syscheck_receiver.php") > len(config["replace_str"]):
        return "Replacement host has to be exactly 48 characters; Specified URL is too short!", 400

    dol = BytesIO()
    zip = BytesIO()

    # hex edit boot.dol
    dol2 = open(f"{os.getcwd()}/static/syscheck2/boot.dol", "rb")
    dol.write(dol2.read().replace("http://syscheck.softwii.de/syscheck_receiver.php".encode("utf-8"), config["replace_str"].encode("utf-8")))
    dol.seek(0)
    dol2.close()

    zf = zipfile.ZipFile(zip, "w", zipfile.ZIP_DEFLATED, False)
    zf.writestr("apps/syscheck2/boot.dol", dol.read())
    dol.close()
    zf.write(f"{os.getcwd()}/static/syscheck2/icon.png", "apps/syscheck2/icon.png")
    zf.write(f"{os.getcwd()}/static/syscheck2/meta.xml", "apps/syscheck2/meta.xml")
    zf.close()
    zip.seek(0)

    # send zipfile
    return send_file(zip, mimetype="application/zip", as_attachment=True, download_name="syscheck2.1.0.b19v2.zip"), 200

# handle errors
@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(405)
@app.errorhandler(502)
def errorhandler(e):
    if e.code == 400:
        jsonstring = {"message": "Bad Request.", "code": 400, "error": True}
        resp = flask.Response(json.dumps(jsonstring))
        resp.headers["Content-Type"] = "application/json"
        return resp, 400
    elif e.code == 404:
        jsonstring = {"message": "Not found.", "code": 404, "error": True}
        resp = flask.Response(json.dumps(jsonstring))
        resp.headers["Content-Type"] = "application/json"
        return resp, 404
    elif e.code == 405:
        jsonstring = {"message": "Method not allowed.", "code": 405, "error": True}
        resp = flask.Response(json.dumps(jsonstring))
        resp.headers["Content-Type"] = "application/json"
        return resp, 405
    elif e.code == 502:
        jsonstring = {"message": "Bad Gateway.", "code": 502, "error": True}
        resp = flask.Response(json.dumps(jsonstring))
        resp.headers["Content-Type"] = "application/json"
        return resp, 502


# run server
if __name__ == "__main__":
    from waitress import serve

    print(f"syscheck_receiver v{config['version']}")

    # check if sqlite db exist if not make one
    if not os.path.isfile(db_dir):
        print("reports.db missing generating new one...")
        db = sqlite3.connect(db_dir)
        cursor = db.cursor()
        cursor.execute("""CREATE TABLE reports (
                       report_id TEXT,
                       timestamp INTEGER,
                       console_id INTEGER
                       )""")
        db.commit()
        db.close()

    if config["docker"]:
        print("Docker is TRUE")
        if not os.path.isdir(report_dir):
            os.mkdir(report_dir)

    # start server
    if args.debug == "1":
        print("Debug mode: on")
        app.run(host=config["ip"], port=config["port"], debug=True)
    else:
        print(f"Server is running at http://{config['ip']}:{config['port']}/")
        serve(app, host=config["ip"], port=config["port"])
