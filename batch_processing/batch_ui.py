import os
import threading
from tkinter import filedialog, messagebox
import customtkinter as ctk
import pandas as pd

from batch_processing.batch_processor import BatchProcessor
from batch_processing.summary import add_summary_sheet

class BatchUI:
    """
    Handles the UI components for batch processing in the GenAI Evaluator.
    """

    def __init__(self, parent_frame, api_key, api_url, accept_criteria):
        self.parent_frame = parent_frame
        self.api_key = api_key
        self.api_url = api_url
        self.accept_criteria = accept_criteria

        self.batch_processor = BatchProcessor(api_key, api_url, accept_criteria)

        # File paths
        self.uploaded_file_path = None
        self.processed_file_path = None

        # Status variables
        self.is_processing = False
        self.processing_thread = None

        # Setup UI components
        self.setup_ui()

    def setup_ui(self):
        # Main batch frame
        self.batch_frame = ctk.CTkFrame(self.parent_frame)
        self.batch_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Title
        title_frame = ctk.CTkFrame(self.batch_frame, fg_color="transparent")
        title_frame.pack(fill="x", pady=(10, 20), padx=20)
        ctk.CTkLabel(
            title_frame,
            text="Batch Processing",
            font=("Arial", 16, "bold")
        ).pack(side="left")

        # File selection and buttons row
        file_frame = ctk.CTkFrame(self.batch_frame, fg_color="transparent")
        file_frame.pack(fill="x", padx=20, pady=(0, 10))

        # Upload button
        self.upload_button = ctk.CTkButton(
            file_frame,
            text="Upload Excel",
            command=self.upload_excel,
            fg_color="#007bff",
            hover_color="#0069d9",
            width=120
        )
        self.upload_button.pack(side="left", padx=(0, 10))

        # File path display
        self.file_label = ctk.CTkLabel(
            file_frame,
            text="No file selected",
            font=("Arial", 12),
            text_color="gray"
        )
        self.file_label.pack(side="left", fill="x", expand=True)

        # Download button
        self.download_button = ctk.CTkButton(
            file_frame,
            text="Download Results",
            command=self.download_results,
            fg_color="#6c757d",
            hover_color="#5a6268",
            width=120,
            state="disabled"
        )
        self.download_button.pack(side="right")


        # Progress frame
        self.progress_frame = ctk.CTkFrame(self.batch_frame, fg_color="transparent")
        self.progress_frame.pack(fill="x", padx=20, pady=(10, 0))

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.pack(fill="x", pady=(5, 0))
        self.progress_bar.set(0)

        # Status label
        self.status_label = ctk.CTkLabel(
            self.progress_frame,
            text="Ready",
            font=("Arial", 12)
        )
        self.status_label.pack(pady=(5, 10))

        # New left-aligned "Run Batch" button
        self.batch_button = ctk.CTkButton(
            self.batch_frame,
            text="Run Batch",
            command=self.run_batch_evaluation,
            fg_color="#28a745",
            hover_color="#218838",
            width=100,
            height=30,
            state="disabled"
        )
        self.batch_button.pack(pady=(10, 0), anchor="w", padx=20)

    def upload_excel(self):
        """Handle Excel file upload."""
        file_path = filedialog.askopenfilename(
            title="Select Excel File",
            filetypes=[("Excel files", "*.xlsx *.xls")]
        )

        if not file_path:
            return

        # Validate the Excel file
        is_valid, error_message = self.batch_processor.validate_excel(file_path)

        if not is_valid:
            messagebox.showerror("Invalid Excel File", error_message)
            return

        # Update UI
        self.uploaded_file_path = file_path
        filename = os.path.basename(file_path)
        self.file_label.configure(text=f"Selected: {filename}", text_color="white")
        self.batch_button.configure(state="normal")
        self.download_button.configure(state="disabled")
        self.processed_file_path = None

    def run_batch_evaluation(self):
        """Run batch evaluation on the uploaded Excel file."""
        if not self.uploaded_file_path or self.is_processing:
            return

        self.is_processing = True
        self.update_ui_processing_started()

        # Start processing in a separate thread
        self.processing_thread = threading.Thread(
            target=self._process_batch,
            daemon=True
        )
        self.processing_thread.start()

    def _process_batch(self):
        """Process the batch in a separate thread."""
        try:
            # Process the batch
            df, elapsed_time = self.batch_processor.process_batch(
                self.uploaded_file_path,
                progress_callback=self.update_progress
            )

            # Save results to a temporary file
            output_dir = os.path.dirname(self.uploaded_file_path)
            base_name = os.path.splitext(os.path.basename(self.uploaded_file_path))[0]
            self.processed_file_path = os.path.join(output_dir, f"{base_name}_results.xlsx")

            # Save with summary sheet
            with pd.ExcelWriter(self.processed_file_path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Results')
                add_summary_sheet(writer, df)

            # Format elapsed time
            hours, remainder = divmod(elapsed_time, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

            # Update UI on the main thread
            self.parent_frame.after(0, lambda: self.update_ui_processing_completed(True, time_str))

        except Exception as e:
            # Handle errors
            self.parent_frame.after(0, lambda err=str(e): self.update_ui_processing_error(err))

    def update_progress(self, current, total):
        """Update the progress bar."""
        progress = current / total if total > 0 else 0
        self.parent_frame.after(0, lambda: self.progress_bar.set(progress))
        self.parent_frame.after(0, lambda: self.status_label.configure(
            text=f"Processing {current+1} of {total} rows..."
        ))

    def update_ui_processing_started(self):
        """Update UI when processing starts."""
        self.batch_button.configure(state="disabled")
        self.upload_button.configure(state="disabled")
        self.download_button.configure(state="disabled")
        self.progress_bar.set(0)
        self.status_label.configure(text="Starting batch processing...")

    def update_ui_processing_completed(self, success, elapsed_time):
        """Update UI when processing completes."""
        self.is_processing = False
        self.batch_button.configure(state="normal")
        self.upload_button.configure(state="normal")

        if success:
            self.download_button.configure(state="normal")
            self.status_label.configure(
                text=f"Batch processing completed in {elapsed_time}",
                text_color="#28a745"
            )
            self.progress_bar.set(1)
        else:
            self.status_label.configure(
                text="Error saving results",
                text_color="#dc3545"
            )

    def update_ui_processing_error(self, error_message):
        """Update UI when processing encounters an error."""
        self.is_processing = False
        self.batch_button.configure(state="normal")
        self.upload_button.configure(state="normal")
        self.status_label.configure(
            text=f"Error: {error_message}",
            text_color="#dc3545"
        )

    def download_results(self):
        """Handle downloading the processed results."""
        if not self.processed_file_path:
            return

        save_path = filedialog.asksaveasfilename(
            title="Save Results",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=os.path.basename(self.processed_file_path)
        )

        if not save_path:
            return

        try:
            import shutil
            shutil.copy2(self.processed_file_path, save_path)

            self.status_label.configure(
                text=f"Results saved to {os.path.basename(save_path)}",
                text_color="#28a745"
            )
        except Exception as e:
            messagebox.showerror("Download Error", f"Error saving file: {str(e)}")

    def update_accept_criteria(self, new_criteria):
        """Update the acceptance criteria used for batch processing."""
        self.accept_criteria = new_criteria
        self.batch_processor.accept_criteria = new_criteria

    def clear_fields(self):
        """Reset all batch UI elements to their initial state."""
        self.uploaded_file_path = None
        self.processed_file_path = None
        self.file_label.configure(text="No file selected", text_color="gray")
        self.batch_button.configure(state="disabled")
        self.download_button.configure(state="disabled")
        self.progress_bar.set(0)
        self.status_label.configure(text="Ready", text_color="gray")
        self.is_processing = False