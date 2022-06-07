import sqlite3
import re


from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime


app = Flask(__name__)


def today():
    today = datetime.today().strftime("%Y%m%d")
    return today


# Gather the information for forum posts from the database.
# Non specific queries will return multiple rows, fetchall is required
# Specific queires will only return one row so using fetchone is fine
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


# Updates Post table once user submits new post
def update_post(type, title, content, date, like=0, dislike=0, user_id=1):
    conn = sqlite3.connect("forum_database.db")
    cur = conn.cursor()
    cur.execute("""INSERT INTO Post (type, title, content, like, dislike, user_id, date)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (type, title, content, like, dislike, user_id, date))
    conn.commit()
    conn.close()


# Updates comments table once user creates a comment or reply
def update_comment(user_id, post_id, content, date, comment_id=None, like=0, dislike=0):
    conn = sqlite3.connect("forum_database.db")
    cur = conn.cursor()
    cur.execute("""INSERT INTO Comment (user_id, post_id, comment_id, content, like, dislike, date)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, post_id, comment_id, content, like, dislike, date))
    conn.commit()
    conn.close()


# The post tables gets passed to the jinja loop in "home.html".
# This is to create HTML posts for each entry in the post table.
@app.route("/")
def home():
    post = call_database("SELECT * FROM Post")
    return render_template("home.html", post=post)


# Gets the form values from the home page,
# The variables get updated to the database.
# Then the home page then gets refreshed.
@app.route("/create_post", methods=["GET", "POST"])
def create_post():
    if request.method == "POST":
        title = request.form["title"]
        type = request.form["type"]
        content = request.form["content"]
        date = today()
        update_post(type, title, content, date)
        return redirect(url_for("home"), code=302)


# Gets values from each created comment
# Update comment database using given values
# refresh current page
@app.route("/create_comment", methods=["GET", "POST"])
def create_comment():
    if request.method == "POST":
        comment_id = request.form
        

# The page where posts and comments are created
@app.route("/post")
def post():
    type = "thread"
    return render_template("post.html", type=type)


# Directs user to the about page
@app.route("/about")
def about():
    return render_template("about.html")


# The route creates pages dynamically.
# The id variable passed into the call database function.
# Page info is passed into HTML with jinja code
# Comments tied to posts have no comment_id
# Replies are tied to a comment so theres a comment_id
@app.route("/page/<int:id>")
def page(id):
    page_info = call_database("SELECT * FROM Post WHERE id = ?", (id),)
    comment = call_database("SELECT * FROM Comment WHERE comment_id IS NULL")
    reply = call_database("SELECT * FROM Comment WHERE comment_id IS NOT NULL")
    return render_template("page.html",
                           page_info=page_info,
                           comment=comment,
                           reply=reply)


# A page exclusively to search for specific posts.
@app.route("/search")
def search():
    return render_template("search.html")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port="8000")
