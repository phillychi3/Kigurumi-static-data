from init_database import get_password_hash


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("python hash_password.py <password>")
        sys.exit(1)

    password = sys.argv[1]
    hashed = get_password_hash(password)
    print(f"original: {password}")
    print(f"hashed: {hashed}")