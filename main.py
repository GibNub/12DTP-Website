import sqlite3
import re

from time import time
from flask import Flask, render_template, request, redirect, url_for
from markupsafe import Markup

import templates

app = Flask(__name__)

# Same as above.
def comment(user_id, content, like, dislike, date):
    comment_template = """
    <li>
        <div class="comment_op">
            <p>
                {0}
            </p>
        </div>
        <div class="comment_content">
            <p>
                {1}
            </p>
        </div>
        <div class="comment_info">
            <p>
                {2}
            </p>
            <p>
                {3}
            </p>
            <p>
                {4}
            </p>
        </div>
        <div class="replies">
            <ul>
                {{ reply }}
            </ul>
        </div>
    """.format(user_id, content, like, dislike, date)


def reply(user_id, content, like, dislike, date):
    reply_template = """
        <div class="reply">
            <p>
                {0}
            </p>
            <p>
                {1}
            </p>
            <p>
                {2}
            </p>
            <p>
                {3}
            </p>
            <p>
                {4}
            </p>
        </div>
    """.format(user_id, content, like, dislike, date)


# Gather the information for forum posts from the database.
def call_database(query, id=None):
    conn = sqlite3.connect("forum_database.db")
    cur = conn.cursor()
    if id is None:
        cur.execute(query)
        result = cur.fetchall()
    else:
        cur.execute(query, (str(id),))
        result = cur.fetchone()
    conn.close()
    return result


def update_post(type, title, content):
    conn = sqlite3.connect("forum_database.db")
    cur = conn.cursor()
    cur.execute("""INSERT INTO Post (type, title, content, like, dislike, user_id, date)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (type, title, content, 0, 0, 1, 25052022))
    conn.commit()
    conn.close()


# The post tables gets passed to the jinja loop in "home.html".
# This is to create HTML posts for each entry in the post table.
@app.route("/")
def home():
    post = call_database("SELECT * FROM Post")
    return render_template("home.html", post = post)



# This gsets the form values from the home page,
# The variables get updated to the database.
# Then the home page then gets refreshed.
@app.route("/create_post", methods=["GET", "POST"])
def create_post():
    if request.method == "POST":
        title = request.form["title"]
        type = request.form["type"]
        content = request.form["content"]
        update_post(type, title, content)
        return redirect(url_for("home"), code=302)


# Directs user to the about page
@app.route("/about")
def about():
    return render_template("about.html")


# The route creates pages automatically for each pages.
# The id variable passed into the call database function.
@app.route("/page/<int:id>")
def page(id):
    return render_template("page.html",
                           title = call_database("SELECT title FROM Post WHERE id = ?", id)[0],
                           content = call_database("SELECT content FROM Post WHERE id = ?", id)[0],
                           type = call_database("SELECT type FROM Post WHERE id = ?", id)[0],
                           date = call_database("SELECT date FROM Post WHERE id = ?", id)[0],
                           user_id = call_database("SELECT user_id FROM Post WHERE id = ?", id)[0],
                           like = call_database("SELECT like FROM Post WHERE id = ?", id)[0],
                           dislike = call_database("SELECT dislike FROM Post WHERE id = ?", id)[0],
                           )


# A page exclusively to search for specific posts.
@app.route("/search")
def search():
    return render_template()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port="8000")
