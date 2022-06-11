import sqlite3
import re


from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime


app = Flask(__name__)


def today():
    # Format is YYYYMMDD with leading zeros for months and days
    today = datetime.today().strftime("%Y%m%d")
    return today


# Gather the information for forum posts from the database.
# String building may be required in a later date
# All results will be stored as a tuple in a list
# For single item lists, specify with a index of 0
def call_database(query, id=None):
    conn = sqlite3.connect("forum_database.db")
    cur = conn.cursor()
    # Can't have option arguments in .execute function
    # May use string building in the future
    if id is None:
        cur.execute(query)
    else:
        cur.execute(query, (str(id)),)
    result = cur.fetchall()
    return result


# Updates Post table once user submits new post
def update_post(type, title, content, date, user_id, like=0, dislike=0):
    conn = sqlite3.connect("forum_database.db")
    cur = conn.cursor()
    cur.execute("""INSERT INTO Post
                (type, title, content, like, dislike, user_id, date)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (type, title, content, like, dislike, user_id, date))
    conn.commit()
    conn.close()


# Updates comments table once user creates a comment or reply
# like and dislike cannot be null so default value is 0
def update_comment(user_id, post_id, content, date, comment_id=None, like=0, dislike=0):
    conn = sqlite3.connect("forum_database.db")
    cur = conn.cursor()
    cur.execute("""INSERT INTO Comment
                (user_id, post_id, comment_id, content, like, dislike, date)
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
@app.route("/create_post", methods=["GET", "POST"])
def create_post():
    if request.method == "POST":
        title = request.form["title"]
        type = request.form["type"]
        content = request.form["content"]
        date = today()
        update_post(type, title, content, date)
        # Go back to home page so users can easily see their new post
        return redirect(url_for("home"), code=302)


# Gets values from each created comment
# Update comment database using given values
# refresh current page
@app.route("/create_comment", methods=["GET", "POST"])
def create_comment():
    if request.method == "POST":
        pass


# The page where comments are created
@app.route("/comment_to/<int:post_id>")
def post(post_id):
    return render_template("post.html", post_id=post_id, comment_id=None)


# The page where replies are created
@app.route("/reply_to/<int:post_id>/<int:comment_id>")
def post_reply(post_id, comment_id):
    return render_template("post.html", post_id=post_id, comment_id=comment_id)


# Directs user to the about page
@app.route("/about")
def about():
    return render_template("about.html")


# The route creates pages dynamically.
# The id variable passed into the call database function.
# Page info is passed into HTML with jinja code
@app.route("/page/<int:id>")
def page(id):
    # Page_info needs index of 0 as the result is stored in tuple inside a list
    page_info = call_database("SELECT * FROM Post WHERE id = ?", (id),)[0]
    # Comments tied to posts have no comment_id
    comment = call_database("""SELECT * FROM Comment
                            WHERE comment_id IS NULL
                            AND post_id = ?""",
                            (id),)
    # Replies are tied to a comment so theres a comment_id
    reply = call_database("""SELECT * FROM Comment
                          WHERE comment_id IS NOT NULL
                          AND post_id = ?""",
                          (id),)
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
