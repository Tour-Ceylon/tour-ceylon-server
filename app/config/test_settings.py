# test_settings.py

from settings import get_settings

def main():
    settings = get_settings()

    print("DATABASE_URL:", settings.DATABASE_URL)
    # print("CLERK_JWT_PUBLIC_KEY:", settings.CLERK_JWT_PUBLIC_KEY)
    print("CLERK_ISSUER:", settings.CLERK_ISSUER)
    print("CLIENT_APP_URL:", settings.CLIENT_APP_URL)
    print("DEBUG:", settings.DEBUG)
    print("CLERK_JWT_PUBLIC_KEY:", settings.clerk_public_key)

if __name__ == "__main__":
    main()