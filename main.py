import sqlite3
import re

from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime


app = Flask(__name__)


def today():
    # Format is YYYYMMDD with leading zeros for months and days
    # This allows for easy sort by date and string splicing
    today = datetime.today().strftime("%Y%m%d")
    return today


# Gather the information for forum posts from the database.
# String building may be required in a later date
# All results will be stored as a tuple in a list
# For single item lists, specify with a index of 0
def call_database(query, parameter=None):
    conn = sqlite3.connect("forum_database.db")
    cur = conn.cursor()
    # Can't have option arguments in .execute function
    # May use string building in the future
    if parameter is None:
        cur.execute(query)
    else:
        cur.execute(query, parameter)
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


# The route creates pages dynamically.
# The id variable passed into the call database function.
# Page info is passed into HTML with jinja code
@app.route("/page/<int:id>")
def page(id):
    # Page_info needs index of 0 as the result is stored in tuple inside a list
    page_info = call_database("SELECT * FROM Post WHERE id = ?", (str(id)),)[0]
    # Comments tied to posts have no comment_id
    comment = call_database("""SELECT * FROM Comment
                            WHERE comment_id IS NULL
                            AND post_id = ?""",
                            (str(id)),)
    # Replies are tied to a comment so theres a comment_id
    reply = call_database("""SELECT * FROM Comment
                          WHERE comment_id IS NOT NULL
                          AND post_id = ?""",
                          (str(id)),)
    return render_template("page.html",
                           page=page_info,
                           comment=comment,
                           reply=reply)


# Page where user replies to a comment.
@app.route("/page/reply_to/<int:post_id>/<int:comment_id>")
def reply_to(post_id, comment_id):
    reffered_comment = call_database("""SELECT * FROM Comment 
                                     WHERE id = ? 
                                     AND post_id = ?""",
                                     (comment_id, post_id))[0]
    return render_template("reply.html", comment=reffered_comment)


# Directs user to the about page
@app.route("/about")
def about():
    return render_template("about.html")


# A page exclusively to search for specific posts.
@app.route("/search")
def search():
    return render_template("search.html")


# Gets the form values from the home page,
# The variables get updated to the database.
@app.route("/create_post", methods=["GET", "POST"])
def create_post():  
    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]
        type = request.form["type"]
        date = today()
        update_post(type, title, content, date, 1)
        # Go back to home page so users can easily see their new post
        return redirect(request.referrer)


# Gets values from each created comment
# Update comment database using given values
# refresh current page
@app.route("/create_comment", methods=["GET", "POST"])
def create_comment():
    if request.method == "POST":
        content = request.form["comment_content"]
        post_id = request.form["post_id"]
        date = today()
        update_comment(1, post_id, content, date)
        return redirect(request.referrer)


# Update database with reply
@app.route("/reply", methods=["GET", "POST"])
def reply():
    if request.method == "POST":
        content = request.form["content"]
        post_id = request.form["post_id"]
        comment_id = request.form["comment_id"]
        date = today()
        update_comment(1, post_id, content, date, comment_id)
        return redirect(url_for("page", id=post_id))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port="8000")
