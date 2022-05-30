import sqlite3

from time import time
from flask import Flask, render_template, request, redirect, url_for
from markupsafe import Markup


app = Flask(__name__)


# This is the html template for indivdual forum posts.
def forum_post(title, type, date, content, like, dislike, id):
    html_template = """
    <li class="thread">
        <div class="head">
            <h4 class="title">
                <a href="/pages/{6}">{0}</a>
            </h4>
            <h5 class="type">
                {1}
            </h5>
            <p>
                {2}
            </p>
        </div>
        <div class="body">
            <p>{3}</p>
        </div>
        <div class="foot">
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
def comment_and_reply(user_id, content, like, dislike, date):
    comment_template = """
    <li class="comment">
        <div class="comment>
            <h6>
                {0}
            </h6>
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
            <div class="replies">
                {{ reply }}
            </div>
    """.format(user_id, content, like, dislike, date)


# Gather the information for forum posts from the database.
def call_page_database(i):
    conn = sqlite3.connect("forum_database.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM Post WHERE id = ?", (str(i),))
    return cur.fetchone()
    conn.close()


def call_comment_database(i):
    conn = sqlite3.connect("forum_database.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM Comment WHERE post_id = ?", (str(i),))
    return cur.fetchall()
    conn.close()


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
        if call_page_database(i) is None:
            break
        forum_html.append(forum_post(
            call_page_database(i)[2],  # title.
            call_page_database(i)[1],  # type.
            call_page_database(i)[3],  # content.
            call_page_database(i)[4],  # like.
            call_page_database(i)[5],  # dislike.
            call_page_database(i)[7],  # date.
            call_page_database(i)[0],  # id.
        ))
        i += 1
    forum_html = "".join(forum_html)
    forum_html.replace("\n", "")
    forum_html.replace(" ", "")
    forum_html = Markup(forum_html)
    return render_template("home.html", value=forum_html)


# This gets the form values from the home page,
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
@app.route("/pages/<int:id>")
def page(id):
    return render_template("page.html",
                           title=call_page_database(id)[2],  # title.
                           type=call_page_database(id)[1],  # type.
                           content=call_page_database(id)[3],  # content.
                           date=call_page_database(id)[7],  # date.
                           user_id=call_page_database(id)[6],  # user id.
                           like=call_page_database(id)[4],  # like.
                           dislike=call_page_database(id)[5],  # dislike.
                           )


# A page exclusively to search for specific posts.
@app.route("/search")
def search():
    return render_template()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port="8000")
