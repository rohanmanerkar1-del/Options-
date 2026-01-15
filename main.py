from suggestion_engine import suggest_trade

def main():
    print("\n--- ZERODHA ALGO TRADER ---")
    try:
        capital = float(input("Enter Your Capital (₹): "))
        margin = float(input("Enter Available Margin (₹): "))
        suggest_trade(capital, margin)
    except ValueError:
        print("[!] Invalid input. Please enter numeric values.")
    except KeyboardInterrupt:
        print("\n[!] Exited by user.")

if __name__ == "__main__":
    main()
