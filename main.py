import customtkinter as ctk
import threading
import time
import pandas as pd
from tkinter import filedialog, messagebox
from scraper import scrape_google_maps

# Set the modern theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class LeadScraperApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AI Lead Scraper Pro - Portfolio Project")
        self.geometry("700x500")

        # --- UI LAYOUT ---
        self.grid_columnconfigure(0, weight=1)

        # Title Label
        self.label = ctk.CTkLabel(self, text="Google Maps Lead Scraper", font=("Helvetica", 24, "bold"))
        self.label.grid(row=0, column=0, padx=20, pady=20)

        # Input Frame
        self.input_frame = ctk.CTkFrame(self)
        self.input_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")

        self.query_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Keyword (e.g. Dentists)", width=250)
        self.query_entry.grid(row=0, column=0, padx=10, pady=10)

        self.location_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Location (e.g. New York)", width=250)
        self.location_entry.grid(row=0, column=1, padx=10, pady=10)

        # Start/Stop Buttons
        self.start_btn = ctk.CTkButton(self, text="Start Extraction", command=self.start_scraping_thread)
        self.start_btn.grid(row=2, column=0, padx=20, pady=10)

        # Log Window (Shows real-time progress)
        self.log_box = ctk.CTkTextbox(self, height=200, width=600)
        self.log_box.grid(row=3, column=0, padx=20, pady=10)
        self.log_box.insert("0.0", "System Ready...\n")

    def log(self, message):
        """Update the UI log safely."""
        self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_box.see("end")

    def start_scraping_thread(self):
        """Starts the scraper in a separate thread to keep UI responsive."""
        query = self.query_entry.get()
        location = self.location_entry.get()

        if not query or not location:
            messagebox.showwarning("Input Error", "Please fill in both fields!")
            return

        self.start_btn.configure(state="disabled")
        # Start the background task
        threading.Thread(target=self.run_scraper_logic, args=(query, location), daemon=True).start()

    def run_scraper_logic(self, query, location):
        """The actual scraping logic goes here."""
        try:
            self.log(f"Initializing Browser for {query} in {location}...")

            leads = scrape_google_maps(query, location, self.log)

            if not leads:
                self.log("No leads found.")

            self.log("Saving results to Excel...")
            df = pd.DataFrame(leads)
            df.to_excel("leads_output.xlsx", index=False)
            self.log("Scraping Complete!")
            messagebox.showinfo("Success", "Leads exported to 'leads_output.xlsx'")
            
        except Exception as e:
            self.log(f"Error: {str(e)}")
        finally:
            self.start_btn.configure(state="normal")

if __name__ == "__main__":
    app = LeadScraperApp()
    app.mainloop()