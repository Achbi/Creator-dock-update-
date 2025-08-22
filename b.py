import hashlib
import requests
from googlesearch import search  # correct import

def check_gravatar(email):
    """Check if the email has a Gravatar profile."""
    email_hash = hashlib.md5(email.lower().encode()).hexdigest()
    gravatar_url = f"https://www.gravatar.com/{email_hash}.json"
    try:
        response = requests.get(gravatar_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            profile = data.get('entry', [{}])[0]
            return {
                "gravatar_profile": profile.get("profileUrl"),
                "name": profile.get("name", {}).get("formatted")
            }
    except Exception as e:
        print("Error checking Gravatar:", e)
    return None

def google_search_email(email, num_results=5):
    """Perform a Google search for the email."""
    results = []
    try:
        for url in search(f'"{email}"', num_results=num_results, lang="en"):
            results.append(url)
    except Exception as e:
        print("Error during Google search:", e)
    return results

def main():
    email = "iiitcollogue@gmail.com"
    
    print("\nChecking Gravatar...")
    gravatar_info = check_gravatar(email)
    if gravatar_info:
        print("Found Gravatar profile:")
        print(gravatar_info)
    else:
        print("No Gravatar profile found.")
    
    print("\nPerforming Google search...")
    search_results = google_search_email(email)
    if search_results:
        print("Public links found:")
        for result in search_results:
            print(result)
    else:
        print("No public links found.")

if __name__ == "__main__":
    main()
