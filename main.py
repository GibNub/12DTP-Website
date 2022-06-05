import sqlite3
import re

from time import time
from flask import Flask, render_template, request, redirect, url_for
from markupsafe import Markup

import templates

app = Flask(__name__)


# This is the html template for indivdual forum posts.
def forum(forum_info):
    id, type, title, content, like, dislike, user_id, date = forum_info
    html_template = """
    <li>
        <div class="post_head">
            <h4 class="post_title">
                <a href="/pages/{6}">{0}</a>
            </h4>
            <h5 class="post_type">
                {1}
            </h5>
            <p>
                {2}
            </p>
        </div>
        <div class="post_body">
            <p>{3}</p>
        </div>
        <div class="post_foot">
            <p>
                {4}
            </p>
            <p>
                {5}
            </p>
        </div>
    </li>
    """.format(title, type, date, content, like, dislike, id)
    return html_template


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
def call_database(query, i=None):
    conn = sqlite3.connect("forum_database.db")
    cur = conn.cursor()
    if i is None:
        cur.execute(query)
        result = cur.fetchall()
    else:
        cur.execute(query, (str(i),))
        result = cur.fetchone()
    conn.close()
    return result


def call_comment_database(i):
    conn = sqlite3.connect("forum_database.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM Comment WHERE post_id = ?", (str(i),))
    return cur.fetchall()
    conn.close()


def call_reply_database(i):
    conn = sqlite3.connect("forum")


def update_post(type, title, content):
    conn = sqlite3.connect("forum_database.db")
    cur = conn.cursor()
    cur.execute("""INSERT INTO Post (type, title, content, like, dislike, user_id, date)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (type, title, content, 0, 0, 1, 25052022))
    conn.commit()
    conn.close()


# Templates the html forum index with information from the database.
# Then joins them in one string to then be passed to the actual html file.
# This creates the expandable forum.
@app.route("/")
def home():
    # Create the posts on the front page by looping through the database.
    forum_html = []
    i = 1
    while True:
        data = call_database("SELECT * FROM Post WHERE id = ?", i)
        if data is None:
            break
        forum_html.append(forum(data))
        i += 1
    forum_html = "".join(forum_html)
    forum_html.replace("\n", "")
    forum_html.replace(" ", "")
    forum_html = Markup(forum_html)
    return render_template("home.html", value=forum_html)


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


test_post = call_database("SELECT * FROM Post")
for post in test_post:
    print(post)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port="8000")
