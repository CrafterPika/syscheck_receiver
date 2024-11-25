# modules
import flask
import json
import os
import string
import random
import sqlite3
import time
import html
from argparse import ArgumentParser
from flask import Flask, request, render_template, send_file
from datetime import datetime

# stuff
with open(f"{os.getcwd()}/config.json", "r") as f:
    config = json.load(f)

parser = ArgumentParser(prog="syscheck_receiver", description="Server that saves SysCheck report uploads.")
parser.add_argument("-d", "--debug", dest="debug", action='store_true', help="Runs with Flask debug server instead of Waitress. DO NOT USE IN PRODUCTION!!!!")
args = parser.parse_args()

def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

def get_console_id(txt):
    array = txt.split("\n")
    for ln in array:
        if ln.startswith("Console ID: "):
            return ln.split(":")[1][1:]

    return "0"

def return_error(message: string, code: int):
    jsonstring = {"message": message, "code": code, "error": True}
    resp = flask.Response(json.dumps(jsonstring))
    resp.headers["Content-Type"] = "application/json"
    return resp

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

    return render_template("index.html", uploadIndex=uploadIndex, report_count=report_count[0][0], svr_ver=config["version"]), 200

@app.route("/syscheck_up.php", methods=["POST"]) # SysCheckME-dev
@app.route("/syscheck_receiver.php", methods=["POST"]) # literally anything else (DNS?)
def syscheck_report():
    form_data = request.form.to_dict(flat=False)
    report_txt = form_data["syscheck"][0]
    console_id = get_console_id(report_txt)

    # check if console id: is present
    if console_id == "0":
        return "ERROR: Not a valid sysCheck!", 200
    # check if syscheck isn't too small or too large
    if len(report_txt.encode("utf-8")) > 6144:
        return "ERROR: Report is too large! Max is 6KB.", 200
    elif len(report_txt.encode("utf-8")) < 1330:
        return "ERROR: Report is too small! Min is 1.3KB.", 200

    timestamp = int(time.time())
    report_id = id_generator(6, 'AaBbCcDdFfeEgGhHiIjJkKlLmMnNoOpPqQrRsStTuUvVwWXxYyZz1234567890')

    if form_data["password"][0] == config["upload_password"]:
        try:
            with open(f"{report_dir}/{report_id}.csv", "a+") as report:
                report.write(report_txt)

            db = sqlite3.connect(db_dir)
            cursor = db.cursor()
            cursor.execute("INSERT INTO reports VALUES ('{}', {}, {})".format(report_id, timestamp, console_id))
            db.commit()
            db.close()

            return f"Success! Report ID: {report_id}", 200
        except Exception as ex:
            print(ex)
            return "ERROR: Failed to save SysCheck report!", 200
    else:
        return "ERROR: Unauthorized", 200

@app.route("/download_csv", methods=["GET"], defaults={'_route': 'direct'})
@app.route("/view_report", methods=["GET"], defaults={'_route': 'template'})
def view_report(_route):
    report_id = request.args.get("id")
    if os.path.isfile(f"{report_dir}/{report_id}.csv"):
        if _route == "template":
            with open(f"{report_dir}/{report_id}.csv", "r") as report:
                return render_template("view_report.html", report_id=report_id, report_content=html.escape(report.read()), svr_ver=config["version"]), 200
        else:
            return send_file(f"{report_dir}/{report_id}.csv", as_attachment=True, download_name="report.csv")
    else:
        return "Report does not exist.", 404

# handle errors
@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(405)
@app.errorhandler(502)
def errorhandler(e):
    if e.code == 400:
        return return_error("Bad request", 400), 400
    elif e.code == 404:
        return return_error("Not found", 404), 404
    elif e.code == 405:
        return return_error("Method not allowed", 405), 405
    elif e.code == 502:
        return return_error("Bad gateway", 502), 502


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
    if args.debug:
        print("Debug mode: on")
        app.run(host=config["ip"], port=config["port"], debug=True)
    else:
        print(f"Server is running at http://{config['ip']}:{config['port']}/")
        serve(app, host=config["ip"], port=config["port"])
