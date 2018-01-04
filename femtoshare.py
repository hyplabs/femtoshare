#!/usr/bin/python3

"""
Femtoshare
==========

Ultra simple self-hosted file sharing. All files can be accessed/modified by all users. Don't upload anything secret!

Quickstart: run `./femtoshare.py`, then visit `http://localhost:8000/` in your web browser.

See `./femtoshare.py --help` for usage information. See `README.md` for more documentation.
"""

__author__ = "Anthony Zhang (Uberi)"
__version__ = "1.0.4"
__license__ = "MIT"

from http.server import BaseHTTPRequestHandler, HTTPServer
import cgi
import os
import re
import html
import urllib.parse
import argparse
from datetime import datetime
from shutil import copyfileobj

parser = argparse.ArgumentParser()
parser.add_argument("--port", help="local network port to listen on", type=int, default=8000)
parser.add_argument("--public", help="listen on remote network interfaces (allows other hosts to see the website; otherwise only this host can see it)", action="store_true")
parser.add_argument("--files-dir", help="directory to upload/download files from (prefix with # to specify that the path is relative to the Femtoshare executable)", default="#files")
args = parser.parse_args()

if args.public:
    SERVER_ADDRESS = ("0.0.0.0", args.port)
else:
    SERVER_ADDRESS = ("127.0.0.1", args.port)
if args.files_dir.startswith("@"):
    FILES_DIRECTORY = os.path.join(os.path.dirname(os.path.realpath(__file__)), args.files_dir[1:])
else:
    FILES_DIRECTORY = args.files_dir

class FemtoshareRequestHandler(BaseHTTPRequestHandler):
    server_version = "Femtoshare/{}".format(__version__)

    def do_GET(self):
        if self.path == "/":
            self.send_directory_listing()
            return

        # check requested filename
        filename = urllib.parse.unquote(self.path[1:])
        if not self.path.startswith("/") or not self.is_valid_filename(filename):
            self.send_error(400, "Invalid file request")
            return
        self.send_file(filename)

    def do_POST(self):
        # check uploaded file (note that files within cgi.FieldStorage don't need to be explicitly closed)
        try:
            form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers["Content-Type"]})
        except:
            self.send_error(400, "Invalid file upload parameters")
            return

        if "delete_name" in form:  # file delete
            filename = form["delete_name"].value
            if not self.is_valid_filename(filename):
                self.send_error(400, "Invalid filename for file deletion")
                return

            # delete uploaded file from disk
            local_path = os.path.join(FILES_DIRECTORY, filename)
            os.remove(local_path)
        elif "upload_file" in form:  # file upload
            filename = form["upload_file"].filename
            if not self.is_valid_filename(filename):
                self.send_error(400, "Invalid filename for file upload")
                return

            # store uploaded file to disk
            local_path = os.path.join(FILES_DIRECTORY, filename)
            with open(local_path, "wb") as f:
                copyfileobj(form["upload_file"].file, f)
        else:
            self.send_error(400, "Invalid file upload parameters")
            return

        self.send_directory_listing()

    def send_file(self, file_path, headers_only=False):
        try:
            f = open(file_path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return

        try:
            file_info = os.stat(f.fileno())
            self.send_response(200)
            self.send_header("Content-type", "application/octet-stream")
            self.send_header("Content-Length", str(file_info.st_size))
            self.send_header("Last-Modified", self.date_time_string(file_info.st_mtime))
            self.end_headers()
            copyfileobj(f, self.wfile)
        finally:
            f.close()

    def send_directory_listing(self):
        table_entries = []
        try:
            for dir_entry in os.scandir(FILES_DIRECTORY):
                if not dir_entry.is_file(follow_symlinks=False): continue
                file_info = dir_entry.stat()
                table_entries.append((dir_entry.name, file_info.st_size, datetime.fromtimestamp(file_info.st_mtime)))
        except OSError:
            self.send_error(500, "Error listing directory contents")
            return

        response = (
            "<!doctype html>\n" +
            "<html>\n" +
            "    <head>\n" +
            "        <meta charset=\"utf-8\">\n" +
            "        <title>femtoshare</title>\n" +
            "        <style type=\"text/css\">\n" +
            "            body { font-family: monospace; width: 80%; margin: 5em auto; text-align: center; }\n" +
            "            h1 { font-size: 4em; margin: 0; }\n" +
            "            a { color: inherit; }\n" +
            "            table { border-collapse: collapse; width: 100%; }\n" +
            "            table th, table td { border-top: 1px solid #f0f0f0; text-align: left; padding: 0.2em 0.5em; }\n" +
            "            table th { border-top: none; }\n" +
            "            body > form { margin: 1em auto; padding: 1em; display: inline-block; border-top: 0.2em solid black; }\n" +
            "            body > form input { font-family: inherit; margin: 0 1em; }\n" +
            "            table input { font-family: inherit; margin: 0; font-size: 0.8em; }\n" +
            "            p { font-weight: bold; }\n" +
            "        </style>\n" +
            "    </head>\n" +
            "    <body>\n" +
            "        <h1>femtoshare</h1>\n" +
            "        <form enctype=\"multipart/form-data\" method=\"post\"><input name=\"upload_file\" type=\"file\" /><input type=\"submit\" value=\"upload\" /></form>\n" +
            (
                "        <table>\n" +
                "            <thead><tr><th>name</th><th>size</th><th>last modified</th><th>actions</th></tr></thead>\n" +
                "            <tbody>\n" +
                "".join(
                    "                <tr><td><a href=\"{url}\">{name}</a></td><td>{size:,}</td><td>{last_modified}</td><td><form method=\"post\"><input name=\"delete_name\" type=\"hidden\" value=\"{name}\" /><input type=\"submit\" value=\"delete\" /></form></td></tr>\n".format(
                        url=urllib.parse.quote(name), name=html.escape(name), size=size, last_modified=last_modified.isoformat()
                    )
                    for name, size, last_modified in table_entries
                ) +
                "            </tbody>\n" +
                "        </table>\n"
                if table_entries else
                "        <p>(uploaded files will be visible here)</p>\n"
            ) +
            "    </body>\n" +
            "</html>\n"
        )
        response_bytes = response.encode("utf8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def is_valid_filename(self, filename):
        if (os.path.sep is not None and os.path.sep in filename) or (os.path.altsep is not None and os.path.altsep in filename):  # check for filesystem separators
            return False
        if filename in (os.pardir, os.curdir):  # check for reserved filenames
            return False
        if re.match(r"^[\w `!@\$\^\(\)\-=_\[\];',\.]*$", filename) is None:  # check for invalid characters
            return False
        return True

if __name__ == '__main__':
    os.makedirs(FILES_DIRECTORY, exist_ok=True)  # ensure files directory exists
    server = HTTPServer(SERVER_ADDRESS, FemtoshareRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
