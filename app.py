from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from flask_cors import CORS
import requests
import os
import base64
from datetime import datetime
import json

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')
CORS(app)

# Configuration
GITHUB_CLIENT_ID = os.environ.get('GITHUB_CLIENT_ID', 'your-client-id')
GITHUB_CLIENT_SECRET = os.environ.get('GITHUB_CLIENT_SECRET', 'your-client-secret')
GITHUB_OAUTH_URL = 'https://github.com/login/oauth/authorize'
GITHUB_TOKEN_URL = 'https://github.com/login/oauth/access_token'
GITHUB_API_URL = 'https://api.github.com'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    return redirect(f'{GITHUB_OAUTH_URL}?client_id={GITHUB_CLIENT_ID}&redirect_uri={url_for("callback", _external=True)}&scope=repo,user,issues')

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return redirect(url_for('index'))
    
    # Exchange code for access token
    data = {
        'client_id': GITHUB_CLIENT_ID,
        'client_secret': GITHUB_CLIENT_SECRET,
        'code': code,
        'redirect_uri': url_for('callback', _external=True)
    }
    
    response = requests.post(GITHUB_TOKEN_URL, data=data, headers={'Accept': 'application/json'})
    
    if response.status_code == 200:
        access_token = response.json().get('access_token')
        session['access_token'] = access_token
        
        # Get user info
        headers = {'Authorization': f'token {access_token}'}
        user_response = requests.get(f'{GITHUB_API_URL}/user', headers=headers)
        user_data = user_response.json()
        session['username'] = user_data.get('login')
        session['avatar_url'] = user_data.get('avatar_url')
        
        return redirect(url_for('dashboard'))
    else:
        return "Login failed", 400

@app.route('/dashboard')
def dashboard():
    if 'access_token' not in session:
        return redirect(url_for('index'))
    
    headers = {'Authorization': f'token {session["access_token"]}'}
    
    # Get repositories
    repos_response = requests.get(f'{GITHUB_API_URL}/user/repos?sort=updated&per_page=30', headers=headers)
    repos = repos_response.json() if repos_response.status_code == 200 else []
    
    # Get notifications
    notifications_response = requests.get(f'{GITHUB_API_URL}/notifications', headers=headers)
    notifications = notifications_response.json() if notifications_response.status_code == 200 else []
    
    # Get issues assigned to user
    issues_response = requests.get(f'{GITHUB_API_URL}/issues?filter=assigned&per_page=20', headers=headers)
    issues = issues_response.json() if issues_response.status_code == 200 else []
    
    return render_template('dashboard.html', 
                         user=session.get('username'),
                         avatar_url=session.get('avatar_url'),
                         repos=repos, 
                         notifications=notifications,
                         issues=issues)

@app.route('/repo/<owner>/<repo_name>')
def repo_detail(owner, repo_name):
    if 'access_token' not in session:
        return redirect(url_for('index'))
    
    headers = {'Authorization': f'token {session["access_token"]}'}
    
    # Get repo details
    repo_response = requests.get(f'{GITHUB_API_URL}/repos/{owner}/{repo_name}', headers=headers)
    repo = repo_response.json() if repo_response.status_code == 200 else {}
    
    # Get commits
    commits_response = requests.get(f'{GITHUB_API_URL}/repos/{owner}/{repo_name}/commits?per_page=10', headers=headers)
    commits = commits_response.json() if commits_response.status_code == 200 else []
    
    # Get issues
    issues_response = requests.get(f'{GITHUB_API_URL}/repos/{owner}/{repo_name}/issues?state=all&per_page=20', headers=headers)
    issues = issues_response.json() if issues_response.status_code == 200 else []
    
    # Get pull requests
    prs_response = requests.get(f'{GITHUB_API_URL}/repos/{owner}/{repo_name}/pulls?state=all&per_page=20', headers=headers)
    prs = prs_response.json() if prs_response.status_code == 200 else []
    
    # Get README
    readme_response = requests.get(f'{GITHUB_API_URL}/repos/{owner}/{repo_name}/readme', headers=headers)
    readme = ""
    if readme_response.status_code == 200:
        readme_data = readme_response.json()
        readme = base64.b64decode(readme_data.get('content', '')).decode('utf-8') if readme_data.get('content') else ""
    
    # Generate AI insights
    insights = generate_ai_insights(repo, commits, issues, prs)
    
    return render_template('repo_detail.html', 
                         repo=repo, 
                         commits=commits, 
                         issues=issues, 
                         prs=prs, 
                         readme=readme,
                         insights=insights)

@app.route('/api/create-issue', methods=['POST'])
def create_issue():
    if 'access_token' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    headers = {'Authorization': f'token {session["access_token"]}', 'Accept': 'application/json'}
    
    payload = {
        'title': data.get('title'),
        'body': data.get('body', ''),
        'labels': data.get('labels', [])
    }
    
    response = requests.post(
        f"https://api.github.com/repos/{data.get('owner')}/{data.get('repo')}/issues",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 201:
        return jsonify(response.json())
    else:
        return jsonify({'error': 'Failed to create issue'}), 400

@app.route('/api/ai-suggest-labels', methods=['POST'])
def ai_suggest_labels():
    if 'access_token' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    title = data.get('title', '')
    body = data.get('body', '')
    
    labels = suggest_labels(title, body)
    return jsonify({'labels': labels})

@app.route('/api/analyze-repo/<owner>/<repo_name>')
def analyze_repo(owner, repo_name):
    if 'access_token' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    headers = {'Authorization': f'token {session["access_token"]}'}
    
    # Get comprehensive repo data
    repo_response = requests.get(f'{GITHUB_API_URL}/repos/{owner}/{repo_name}', headers=headers)
    repo = repo_response.json() if repo_response.status_code == 200 else {}
    
    contributors_response = requests.get(f'{GITHUB_API_URL}/repos/{owner}/{repo_name}/contributors?per_page=10', headers=headers)
    contributors = contributors_response.json() if contributors_response.status_code == 200 else []
    
    languages_response = requests.get(f'{GITHUB_API_URL}/repos/{owner}/{repo_name}/languages', headers=headers)
    languages = languages_response.json() if languages_response.status_code == 200 else {}
    
    analysis = {
        'repo_name': repo.get('name'),
        'full_name': repo.get('full_name'),
        'description': repo.get('description'),
        'stars': repo.get('stargazers_count', 0),
        'forks': repo.get('forks_count', 0),
        'open_issues': repo.get('open_issues_count', 0),
        'language': repo.get('language'),
        'languages': languages,
        'contributors_count': len(contributors),
        'health_score': calculate_health_score(repo, contributors, languages),
        'recommendations': generate_recommendations(repo, contributors)
    }
    
    return jsonify(analysis)

def calculate_health_score(repo, contributors, languages):
    score = 50
    
    if repo.get('stargazers_count', 0) > 100:
        score += 10
    if repo.get('forks_count', 0) > 10:
        score += 10
    if repo.get('open_issues_count', 0) < 20:
        score += 10
    if contributors:
        score += 10
    if len(languages) > 1:
        score += 10
    if repo.get('description'):
        score += 5
    if repo.get('has_wiki'):
        score += 5
    if repo.get('has_projects'):
        score += 5
    if repo.get('size', 0) > 100:
        score -= 5
    if repo.get('open_issues_count', 0) > 50:
        score -= 10
    
    return min(100, max(0, score))

def generate_recommendations(repo, contributors):
    recommendations = []
    
    if not repo.get('description'):
        recommendations.append("Add a description to help others understand your project")
    if repo.get('open_issues_count', 0) > 30:
        recommendations.append("Consider closing or assigning old issues")
    if not repo.get('has_wiki'):
        recommendations.append("Enable wiki for better documentation")
    if not repo.get('license'):
        recommendations.append("Add a license for open source compliance")
    if len(contributors) < 3:
        recommendations.append("Encourage more contributors to join the project")
    
    return recommendations

def generate_ai_insights(repo, commits, issues, prs):
    insights = {
        'recommendations': [],
        'code_quality': 'Good',
        'activity_level': 'Medium',
        'risk_level': 'Low'
    }
    
    # Analyze commits
    if commits:
        recent_commits = len([c for c in commits[:5] if c.get('commit', {}).get('author', {}).get('date', '') > '2024-01-01'])
        if recent_commits > 3:
            insights['activity_level'] = 'High'
        elif recent_commits == 0:
            insights['activity_level'] = 'Low'
    
    # Analyze issues
    open_issues = [i for i in issues if i.get('state') == 'open']
    if len(open_issues) > 20:
        insights['recommendations'].append("Consider triaging old issues")
        insights['risk_level'] = 'Medium'
    
    # Analyze PRs
    open_prs = [p for p in prs if p.get('state') == 'open']
    if len(open_prs) > 10:
        insights['recommendations'].append("Review open pull requests regularly")
    
    # Check for missing files
    if not repo.get('has_wiki'):
        insights['recommendations'].append("Enable wiki for documentation")
    if not repo.get('license'):
        insights['recommendations'].append("Add an open source license")
    
    return insights

def suggest_labels(title, body):
    labels = []
    text = (title + ' ' + body).lower()
    
    if 'bug' in text or 'error' in text or 'fix' in text:
        labels.append({'name': 'bug', 'color': 'd73a4a'})
    if 'feature' in text or 'request' in text or 'enhancement' in text:
        labels.append({'name': 'enhancement', 'color': 'a2eeef'})
    if 'documentation' in text or 'docs' in text:
        labels.append({'name': 'documentation', 'color': '0075ca'})
    if 'question' in text or 'help' in text:
        labels.append({'name': 'question', 'color': 'd876e3'})
    if 'good first issue' in text or 'beginner' in text:
        labels.append({'name': 'good first issue', 'color': '7057ff'})
    if 'help wanted' in text:
        labels.append({'name': 'help wanted', 'color': '008672'})
    
    return labels

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)