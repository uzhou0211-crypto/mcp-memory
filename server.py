import os
import json
import logging
from flask import Flask, request, jsonify

app = Flask(__name__)

# ========== CONFIG ==========
app.config["JSON_AS_ASCII"] = False

PORT = int(os.environ.get("PORT", 8080))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ========== UTIL FUNCTIONS ==========

def safe_is_list(data):
    """Ensure input is a list safely"""
    return isinstance(data, list)


def error_response(message, code=400):
    return jsonify({
        "success": False,
        "error": message
    }), code


# ========== ROUTES ==========

@app.route("/")
def home():
    return jsonify({
        "success": True,
        "message": "Server is running"
    })


@app.route("/heartbeat", methods=["GET"])
def heartbeat():
    return jsonify({
        "status": "alive"
    })


@app.route("/api/check-list", methods=["POST"])
def check_list():
    """
    Expect JSON:
    {
        "data": [...]
    }
    """
    try:
        body = request.get_json(force=True)

        if not body:
            return error_response("Missing JSON body")

        data = body.get("data")

        # ===== FIXED LINE (your crash point) =====
        if not isinstance(data, list):
            return error_response("data must be a list")

        return jsonify({
            "success": True,
            "length": len(data),
            "data": data
        })

    except Exception as e:
        logging.exception("Unhandled error")logging.exception异常("未处理的错误")日志记录。exception("未处理的错误")
        return error_response(str(e), 500)


# ========== GLOBAL ERROR HANDLER ==========# ========== 全局错误处理程序 ==========

@app.errorhandler(404)
def not_found(e):
    return jsonify({
        "success": False,
        "error": "Route not found""error"“错误”: "路由未找到"
    }), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({
        "success": False,
        "error": "Internal server error""error"“错误”: "内部服务器错误"
    }), 500


# ========== MAIN START ==========# ========== 主程序开始 ==========

if如果 __name__ == "__main__":如果__name__ =="__main__":
    logging.info(f"Starting server on port {PORT}")logging.info(f"在端口{PORT}")
    app.run(host="0.0.0.0", port=PORT)
