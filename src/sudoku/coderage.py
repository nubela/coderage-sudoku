from random import randint, choice
import string
import uuid
from flask import Flask, request, jsonify, json
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy import asc
from sqlalchemy.sql.expression import desc
import time


MIN_PUZZLES_TO_QUALIFY = 50
SQL_URI = 'postgresql://nubela@localhost/coderage'
CHARS = string.ascii_letters + string.digits # the characters to make up the random password

#--- private vars ---

__author__ = 'nubela'
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = SQL_URI
db = SQLAlchemy(app)

#--- db schema ---

class CRUser(db.Model):
    id = db.Column(db.Unicode(255), primary_key=True)
    username = db.Column(db.Unicode(255))
    solved_puzzles_count = db.Column(db.Integer)


class Puzzle(db.Model):
    id = db.Column(db.Unicode(255), primary_key=True)
    user_id = db.Column(db.Unicode(255), db.ForeignKey('cr_user.id'))
    incomplete_puzzle = db.Column(db.Unicode(255))
    complete_puzzle = db.Column(db.Unicode(255))
    timestamp = db.Column(db.Float)

    @property
    def serialize(self):
        return {
            "puzzle": json.loads(self.incomplete_puzzle),
            "id": self.id
        }


class SolvedPuzzle(db.Model):
    id = db.Column(db.Unicode(255), primary_key=True)
    created_user_id = db.Column(db.Unicode(255), db.ForeignKey('cr_user.id'))
    puzzle_id = db.Column(db.Unicode(255), db.ForeignKey('puzzle.id'))
    timestamp = db.Column(db.Float)

#--- api endpoints ---


@app.route('/user/', methods=['PUT'])
def put_user():
    username = request.form.get("username", None)

    #check error
    if get_user_username(username) is not None:
        return jsonify({
            "status": "error",
            "error": "user alr exists"
        })

    if username is None:
        return jsonify({
            "status": "error",
            "error": "no username provided"
        })

    user = new_user(username)

    return jsonify({
        "status": "ok",
        "user_id": user.id,
    })


@app.route('/user/ranks/', methods=['get'])
def get_user_ranks():
    users = (db.session.query(CRUser).
             order_by(desc(CRUser.solved_puzzles_count))
        )
    all_users = users.all()
    serialized_users = []
    for rank, u in enumerate(all_users):
        serialized_users += [{
                                 "rank": rank+1,
                                 "username": u.username,
                                 "puzzles_solved": u.solved_puzzles_count,
                                 "puzzles_uploaded": get_puzzle_count_from_user(u.id),
                             }]
    return jsonify({
        "status": "ok",
        "rankings": serialized_users
    })


@app.route('/sudoku/puzzle/', methods=['PUT'])
def put_sudoku_puzzle():
    user_id = request.form.get("user_id", None)
    incomplete_puzzle_json = request.form.get("incomplete_puzzle", None)
    incomplete_puzzle = json.loads(incomplete_puzzle_json) if incomplete_puzzle_json is not None else None
    complete_puzzle_json = request.form.get("complete_puzzle", None)
    complete_puzzle = json.loads(complete_puzzle_json) if complete_puzzle_json is not None else None
    user = get_user_userid(user_id)

    if 0 in complete_puzzle:
        return jsonify({"status": "error", "error": "solution is erroneous"})
    if user is None:
        return jsonify({"status": "error", "error": "erroneous user id"})
    if incomplete_puzzle_json is None or complete_puzzle_json is None:
        return jsonify({"status": "error", "error": "missing puzzles"})
    if not proper_puzzle(complete_puzzle) or not matches_puzzle(incomplete_puzzle, complete_puzzle):
        return jsonify({"status": "error", "error": "invalid puzzles"})
    if not get_puzzle_from_complete(complete_puzzle_json) is not None:
        new_puzzle(complete_puzzle_json, incomplete_puzzle_json, user_id)
    else:
        return jsonify({"status": "error", "error": "puzzle exists"})

    return jsonify({
        "status": "ok"
    })


@app.route('/sudoku/puzzle/', methods=['GET'])
def httpget_sudoku_puzzle():
    user_id = request.args.get("user_id", None)
    user = get_user_userid(user_id)
    puzzle_count = get_puzzle_count_from_user(user_id)

    if user is None:
        return jsonify({"status": "error", "error": "erroneous user id"})
    if puzzle_count < MIN_PUZZLES_TO_QUALIFY:
        return jsonify({"status": "error",
                        "error": "please submit %d puzzles to qualify. you have currently uploaded %d puzzles" % (
                        MIN_PUZZLES_TO_QUALIFY, puzzle_count)})

    puzzles = db.session.query(Puzzle).filter(Puzzle.user_id != user_id).order_by(asc(Puzzle.timestamp)).limit(
        puzzle_count).all()
    return jsonify({"status": "ok",
                    "puzzles": [p.serialize for p in puzzles]})


@app.route('/sudoku/puzzle/', methods=['POST'])
def post_sudoku_puzzle():
    user_id = request.form.get("user_id", None)
    puzzle_id = request.form.get("puzzle_id", None)
    puzzle = get_puzzle(puzzle_id)
    incomplete_puzzle = json.loads(puzzle.incomplete_puzzle) if puzzle is not None else None
    completed_puzzle_json = request.form.get("complete_puzzle", None)
    completed_puzzle = json.loads(completed_puzzle_json)
    user = get_user_userid(user_id)
    puzzle_count = get_puzzle_count_from_user(user_id)

    if user is None:
        return jsonify({"status": "error", "error": "erroneous user id"})
    if puzzle_count < MIN_PUZZLES_TO_QUALIFY:
        return jsonify({"status": "error",
                        "error": "please submit %d puzzles to qualify. you have currently uploaded %d puzzles" % (
                        MIN_PUZZLES_TO_QUALIFY, puzzle_count)})
    if 0 in completed_puzzle:
        return jsonify({"status": "error", "error": "solution is erroneous"})
    if get_solution_record(puzzle_id, user_id) is not None:
        return jsonify({"status": "error", "error": "you already solved this puzzle"})
    if puzzle is None:
        return jsonify({"status": "error", "error": "erroneous puzzle id"})
    if puzzle.user_id == user_id:
        return jsonify({"status": "error", "error": "cannot solve own puzzles"})
    if matches_puzzle(incomplete_puzzle, completed_puzzle) and proper_puzzle(completed_puzzle):
        new_solution_record(user_id, puzzle_id)
        return jsonify({"status": "ok"})
    else:
        return jsonify({"status": "error", "error": "bad puzzle solution"})

#--- util methods ---

def get_puzzle_count_from_user(user_id):
    return db.session.query(Puzzle).filter(Puzzle.user_id == user_id).count()


def new_user(username):
    #create the user
    user = CRUser()
    user.id = generate_uuid()
    user.username = username
    user.solved_puzzles_count = 0
    db.session.add(user)
    db.session.commit()
    return user


def new_puzzle(complete_puzzle_json, incomplete_puzzle_json, user_id):
    puzzle = Puzzle()
    puzzle.id = generate_uuid()
    puzzle.complete_puzzle = complete_puzzle_json
    puzzle.incomplete_puzzle = incomplete_puzzle_json
    puzzle.user_id = user_id
    puzzle.timestamp = time.time()
    db.session.add(puzzle)
    db.session.commit()
    return puzzle


def get_puzzle_from_complete(complete_puzzle_json):
    p = (db.session.query(Puzzle).
         filter(Puzzle.complete_puzzle == complete_puzzle_json))
    return p.first()


def get_solution_record(puzzle_id, user_id):
    r = (db.session.query(SolvedPuzzle).
         filter(SolvedPuzzle.puzzle_id == puzzle_id).
         filter(SolvedPuzzle.created_user_id == user_id)
        ).first()
    return r


def new_solution_record(user_id, puzzle_id):
    user = get_user_userid(user_id)
    user.solved_puzzles_count += 1

    record = SolvedPuzzle()
    record.created_user_id = user_id
    record.id = generate_uuid()
    record.puzzle_id = puzzle_id
    record.timestamp = time.time()

    db.session.add(user)
    db.session.add(record)
    db.session.commit()
    return record


def random_string():
    """ Create a string of random length between 8 and 16
        characters long, made up of numbers and letters.
    """
    return "".join(choice(CHARS) for x in range(randint(8, 16)))


def generate_uuid():
    return str(uuid.uuid1())


def get_user_username(username):
    return db.session.query(CRUser).filter(CRUser.username == username).first()


def get_user_userid(user_id):
    return db.session.query(CRUser).filter(CRUser.id == user_id).first()


def get_puzzle(puzzle_id):
    return db.session.query(Puzzle).filter(Puzzle.id == puzzle_id).first()


def proper_puzzle(puzzle_lis):
    """
    Checks that this sudoku puzzle fulfills the puzzle constraints and hence is a valid puzzle
    """
    if len(puzzle_lis) != 81:
        return False

    #row constraint
    rows = [puzzle_lis[x * 9:x * 9 + 9] for x in range(9)]
    if len(rows) != 9: return False
    for r in rows:
        if len(set(r)) < 9: return False

    #col constraint
    cols = [puzzle_lis[x::9] for x in range(9)]
    if len(cols) != 9: return False
    for c in cols:
        if len(set(c)) < 9: return False

    #subsquare constraint
    subsquares = []
    for i in range(9):
        general_row = i / 3 * 3
        general_col = (i % 3) * 3
        s = []
        fetched_rows = [rows[j] for j in range(general_row, general_row + 3)]
        for r in fetched_rows:
            for k in range(general_col, general_col + 3):
                s += [r[k]]
        subsquares += [s]
    for s in subsquares:
        if len(s) < 9: return False

    #is proper puzzle
    return True


def matches_puzzle(incomplete_puzzle, completed_puzzle):
    """
    Checks that the incomplete puzzle is a subset of the completed puzzle
    """
    for idx, val in enumerate(incomplete_puzzle):
        if val == 0: continue
        if completed_puzzle[idx] != val:
            return False
    return True


def init_db(db):
    """
    creates the tables from schema
    """
    db.create_all()

if __name__ == "__main__":
    init_db(db)