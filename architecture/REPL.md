This is a brilliant go-to-market strategy. Offering a free trial is the ultimate sales tool because it allows an agency's data science team to prove to their IT department that your engine actually works before they ask for budget approval.

When dealing with government agencies or large enterprises, you face a unique challenge: You cannot use online license validation. Many enterprise servers are "air-gapped" (no internet access). If your CLI tries to ping a server to verify a license key, their firewall will block it, and the software will crash.

To enforce commercial restrictions and a free trial entirely offline, you must use Cryptographic License Keys (Asymmetric Encryption) combined with a Freemium Fallback.

Here is the exact architecture to implement this in your novasurvey-cli.exe.

1. The Strategy: The "Row-Limited" Free Trial
Instead of a time-based trial (which users can hack just by changing their computer's clock), the industry standard for data tools is a Volume Limit.

If a user runs the CLI without a license key, the engine works perfectly, but it will only process a maximum of10,000 rows. This is enough for a statistician to test the math, but useless for a government agency trying to process a 5-million-row national census.

To unlock the engine for unlimited rows, they must provide a cryptographically signed License Key.

2. The Cryptographic Implementation (JSON Web Tokens)
You can use the PyJWT library to generate highly secure, offline-verifiable license keys.

Your Secret Server: You keep a Private Key on your secure machine. When an enterprise pays you, you use the Private Key to generate a token (a long string of characters) that contains their company name and an expiration date.

The CLI: You embed the Public Key inside your Typer CLI. The CLI can read the token to verify it was genuinely created by you, but users cannot generate their own tokens.

3. Updating Your Typer CLI
Here is how you update the cli.py file we built earlier to enforce this logic.

Python
import typer
import polars as pl
import jwt
from datetime import datetime, timezone

# Your public key (Safe to embed in the compiled .exe)
PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
-----END PUBLIC KEY-----"""

def verify_license(license_key: str) -> bool:
    """Verifies the cryptographically signed license offline."""
    if not license_key:
        return False
    try:
        # The CLI verifies the key using the Public Key.
        # If it is expired, PyJWT automatically throws an ExpiredSignatureError.
        payload = jwt.decode(license_key, PUBLIC_KEY, algorithms=["RS256"])
        typer.echo(f"✅ Commercial License Verified: {payload.get('company')}")
        return True
    except jwt.ExpiredSignatureError:
        typer.echo("❌ License Error: Your commercial license has expired.", err=True)
        raise typer.Exit(code=1)
    except jwt.InvalidTokenError:
        typer.echo("❌ License Error: Invalid license key.", err=True)
        raise typer.Exit(code=1)

@app.command()
def run_pipeline(
    module: str = typer.Option(..., help="Module to execute"),
    data_path: str = typer.Option(..., help="Path to Parquet file"),
    license_key: str = typer.Option(None, envvar="NOVASURVEY_LICENSE", help="Commercial License Key")
):
    # 1. Check License Status
    is_commercial = verify_license(license_key)

    # 2. Load Data
    df = pl.read_parquet(data_path)
    total_rows = df.height

    # 3. Enforce The Free Trial Logic
    TRIAL_LIMIT = 10000
    if not is_commercial:
        typer.echo("⚠️ Running in Free Trial Mode.")
        if total_rows > TRIAL_LIMIT:
            typer.echo(f"⚠️ Trial Restriction: Limiting dataset from {total_rows} to {TRIAL_LIMIT} rows.")
            df = df.head(TRIAL_LIMIT)

    # 4. Run the Heavy Math
    typer.echo(f"Processing {df.height} rows...")
    # ... route to your Cython-compiled modules ...
Why this is the ultimate enterprise solution:
Frictionless Adoption: A user can download your .exe from GitHub and immediately test novasurvey-cli --module variance --data_path test.parquet. They see how fast and accurate it is on a small dataset without ever talking to a salesperson.

Environment Variable Support: Notice the envvar="NOVASURVEY_LICENSE" in the Typer command. This allows an IT department to save the license key securely in their server's environment variables, so they don't have to type it out in every single automated script.

Time-Bomb Capability: When you generate the JWT for an enterprise client, you can set the exp (expiration) payload to exactly 365 days. If they don't renew their contract next year, the CLI will automatically revert to the 10,000-row free trial mode.
