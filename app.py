from flask import Flask, render_template_string
import os

app = Flask(__name__)

@app.route('/')
def home():
    return render_template_string(
        '''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Mukera App</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background: #f4f6f8; }
                .container { background: white; padding: 2em; border-radius: 8px; box-shadow: 0 2px 6px #ccc; max-width: 500px; margin: auto; }
                h1 { color: #2c3e50; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Welcome to Mukera App!</h1>
                <p>This is a one-page Python web app ready for Render and Git deployment.</p>
            </div>
        </body>
        </html>
        '''
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
