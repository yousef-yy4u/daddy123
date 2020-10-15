from flask import Blueprint
from flask import render_template


posts = Blueprint('posts', __name__)


@posts.route('/posts', methods=['GET', 'POST'])
def post():
    return render_template('PostPage.html')

