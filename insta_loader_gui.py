import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import subprocess
import threading
import os
import shlex

class InstaloaderGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Instaloader GUI")
        self.geometry("1000x800") 

        self._setup_styles()
        self.option_vars = {}
        self.target_type_var = tk.StringVar(value="profile") 

        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Top Controls ---
        top_controls_frame = ttk.Frame(main_frame)
        top_controls_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(top_controls_frame, text="Instaloader Cmd:", style="Bold.TLabel").pack(side=tk.LEFT, padx=(0, 5))
        self.executable_var = tk.StringVar(value="instaloader") # Default if in PATH
        self.executable_entry = ttk.Entry(top_controls_frame, textvariable=self.executable_var, width=20)
        self.executable_entry.pack(side=tk.LEFT, padx=(0, 15))
        self.executable_var.trace_add("write", self._update_command_preview)

        ttk.Label(top_controls_frame, text="Target(s):", style="Bold.TLabel").pack(side=tk.LEFT, padx=(0, 5))
        self.targets_var = tk.StringVar()
        self.targets_entry = ttk.Entry(top_controls_frame, textvariable=self.targets_var, width=50)
        self.targets_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.targets_var.trace_add("write", self._update_command_preview)

        # --- Notebook for Options ---
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self._create_tabs()

        # --- Command Preview ---
        ttk.Label(main_frame, text="Command Preview:", style="Bold.TLabel").pack(anchor=tk.W)
        self.command_preview_text = scrolledtext.ScrolledText(main_frame, height=3, wrap=tk.WORD,
                                                              font=self.font_text_area, relief=tk.SOLID, borderwidth=1)
        self.command_preview_text.pack(fill=tk.X, pady=(0, 10))
        self.command_preview_text.configure(state='disabled')

        # --- Action Buttons ---
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X)
        self.generate_cmd_button = ttk.Button(controls_frame, text="Preview Command", command=self._update_command_preview_button_action)
        self.generate_cmd_button.pack(side=tk.LEFT, padx=5)
        self.run_button = ttk.Button(controls_frame, text="Run Instaloader", command=self._run_command)
        self.run_button.pack(side=tk.LEFT, padx=5)
        self.clear_button = ttk.Button(controls_frame, text="Clear All Fields", command=self._clear_all_fields)
        self.clear_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = ttk.Button(controls_frame, text="Stop Process", command=self._stop_process, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # --- Output Area ---
        ttk.Label(main_frame, text="Output:", style="Bold.TLabel").pack(anchor=tk.W, pady=(10,0))
        self.output_text = scrolledtext.ScrolledText(main_frame, height=10, wrap=tk.WORD,
                                                     font=self.font_text_area, relief=tk.SOLID, borderwidth=1)
        self.output_text.pack(fill=tk.BOTH, expand=True)
        self.output_text.configure(state='disabled')
        
        self.process = None
        self._update_command_preview()

    def _setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.font_label = ("Arial", 10)
        self.font_label_bold = ("Arial", 10, "bold")
        self.font_entry = ("Arial", 10)
        self.font_button = ("Arial", 11, "bold")
        self.font_text_area = ("Courier New", 9)
        self.style.configure("TLabel", font=self.font_label)
        self.style.configure("Bold.TLabel", font=self.font_label_bold)
        self.style.configure("TEntry", font=self.font_entry, padding=3)
        self.style.configure("TButton", font=self.font_button, padding=5)
        self.style.map("TButton", foreground=[('disabled', 'grey')], background=[('active', '#e0e0e0')])
        self.style.configure("TNotebook", tabposition='nw')
        desired_tab_padding = [20, 5] # Adjusted
        self.style.configure("TNotebook.Tab", font=self.font_label_bold, padding=desired_tab_padding)
        self.style.map("TNotebook.Tab", padding=[('selected', desired_tab_padding), ('active', desired_tab_padding)])
        self.style.configure("TLabelframe", padding=10)
        self.style.configure("TLabelframe.Label", font=self.font_label_bold)
        self.style.configure("TCheckbutton", font=self.font_label)
        self.style.configure("TRadiobutton", font=self.font_label)

    def _create_tabs(self):
        tabs_config = {
            "What to Download (Posts)": self._create_what_posts_tab,
            "What to Download (Profile)": self._create_what_profile_tab,
            "Login & Session": self._create_login_tab,
            "Filtering & Which Posts": self._create_filtering_tab,
            "File & Path Options": self._create_path_options_tab,
            "Connection & Misc": self._create_connection_misc_tab,
        }
        for name, method in tabs_config.items():
            tab = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(tab, text=name)
            method(tab)

    def _add_option_widget(self, parent, label_text, option_key, widget_type="entry", default_value="", browse_type=None, col_span=1, placeholder=None, trace_update=True, var_type=tk.StringVar):
        row = parent.grid_size()[1]
        ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        current_var = None
        widget = None

        if widget_type == "entry":
            initial_text = placeholder if placeholder and str(default_value) == "" else str(default_value)
            current_var = var_type(value=initial_text)
            widget = ttk.Entry(parent, textvariable=current_var, width=40)
            widget.grid(row=row, column=1, sticky=tk.EW, padx=5, pady=2, columnspan=col_span)
            if browse_type:
                ttk.Button(parent, text="Browse", width=8, command=lambda v=current_var, bt=browse_type: self._browse(v, bt)).grid(row=row, column=1+col_span, sticky=tk.W, padx=5, pady=2)
        elif widget_type == "checkbutton":
            current_var = tk.BooleanVar(value=bool(default_value))
            widget = ttk.Checkbutton(parent, variable=current_var, command=self._update_command_preview_button_action if trace_update else None)
            widget.grid(row=row, column=1, sticky=tk.W, padx=5, pady=2, columnspan=col_span)
        elif widget_type == "spinbox":
            current_var = tk.IntVar(value=int(default_value) if default_value else 0) # Assuming int for count
            widget = ttk.Spinbox(parent, from_=0, to=99999, textvariable=current_var, width=10, command=self._update_command_preview_button_action if trace_update else None)
            widget.grid(row=row, column=1, sticky=tk.W, padx=5, pady=2, columnspan=col_span)

        if current_var:
            self.option_vars[option_key] = current_var
            if trace_update and isinstance(current_var, (tk.StringVar, tk.IntVar)): 
                 current_var.trace_add("write", self._update_command_preview)
        parent.grid_columnconfigure(1, weight=1)
        return widget

    def _browse(self, var, browse_type):
        initial = os.path.dirname(var.get()) if var.get() and os.path.exists(os.path.dirname(var.get())) else os.path.expanduser("~")
        path = None
        if browse_type == "directory": path = filedialog.askdirectory(initialdir=initial)
        elif browse_type == "file": path = filedialog.askopenfilename(initialdir=initial)
        elif browse_type == "savefile": path = filedialog.asksaveasfilename(initialdir=initial)
        if path: var.set(path)

    def _create_special_target_selector(self, parent):
        lf = ttk.LabelFrame(parent, text="Special Targets (Overrides Target(s) field if selected)", padding=10)
        lf.grid(row=parent.grid_size()[1], column=0, columnspan=3, sticky="ew", pady=10)
        
        special_targets = [
            ("Profile/Hashtag/Location ID (default)", "profile"),
            (":feed (Your Feed)", ":feed"),
            (":stories (Followee Stories)", ":stories"),
            (":saved (Your Saved Posts)", ":saved")
        ]
        self.target_type_var.set("profile") 

        for text, value in special_targets:
            rb = ttk.Radiobutton(lf, text=text, variable=self.target_type_var, value=value, command=self._update_command_preview_button_action)
            rb.pack(anchor="w", pady=1)
        
        def toggle_target_entry_state(*args):
            if self.target_type_var.get() != "profile":
                self.targets_entry.config(state=tk.DISABLED)
                self.targets_entry.delete(0, tk.END) # Clear it
            else:
                self.targets_entry.config(state=tk.NORMAL)
        self.target_type_var.trace_add("write", toggle_target_entry_state)
        toggle_target_entry_state() 

    def _create_what_posts_tab(self, parent):
        self._create_special_target_selector(parent) 
        
        self._add_option_widget(parent, "Download Comments (-C):", "--comments", widget_type="checkbutton")
        self._add_option_widget(parent, "Download Geotags (-G):", "--geotags", widget_type="checkbutton")
        self._add_option_widget(parent, "NO Pictures:", "--no-pictures", widget_type="checkbutton")
        self._add_option_widget(parent, "NO Videos (-V):", "--no-videos", widget_type="checkbutton")
        self._add_option_widget(parent, "NO Video Thumbnails:", "--no-video-thumbnails", widget_type="checkbutton")
        self._add_option_widget(parent, "NO Captions:", "--no-captions", widget_type="checkbutton")
        self._add_option_widget(parent, "NO Metadata JSON:", "--no-metadata-json", widget_type="checkbutton")
        self._add_option_widget(parent, "NO Compress JSON:", "--no-compress-json", widget_type="checkbutton")
        self._add_option_widget(parent, "Post Metadata Txt Template:", "--post-metadata-txt", col_span=2)
        self._add_option_widget(parent, "StoryItem Metadata Txt Template:", "--storyitem-metadata-txt", col_span=2)
        self._add_option_widget(parent, "Slide (Sidecar):", "--slide", placeholder="e.g., 0, 1-3, 1:")

    def _create_what_profile_tab(self, parent):
        self._add_option_widget(parent, "NO Posts:", "--no-posts", widget_type="checkbutton")
        self._add_option_widget(parent, "NO Profile Pic:", "--no-profile-pic", widget_type="checkbutton")
        self._add_option_widget(parent, "Download Stories (-s):", "--stories", widget_type="checkbutton")
        self._add_option_widget(parent, "Download Highlights:", "--highlights", widget_type="checkbutton")
        self._add_option_widget(parent, "Download Tagged Posts:", "--tagged", widget_type="checkbutton")
        self._add_option_widget(parent, "Download Reels:", "--reels", widget_type="checkbutton")
        self._add_option_widget(parent, "Download IGTV:", "--igtv", widget_type="checkbutton")

    def _create_login_tab(self, parent):
        self._add_option_widget(parent, "Login Username (-l):", "--login")
        self._add_option_widget(parent, "Password (-p):", "--password", placeholder="Will prompt if empty & needed", trace_update=False)

        
        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(row=parent.grid_size()[1], column=0, columnspan=3, sticky="ew", pady=10)
        self._add_option_widget(parent, "Load Cookies From Browser (-b):", "--load-cookies", placeholder="e.g., firefox, chrome")
        self._add_option_widget(parent, "Cookie File (-B):", "--cookiefile", browse_type="file")
        self._add_option_widget(parent, "Session File (-f):", "--sessionfile", browse_type="file", placeholder="Default: AppData/Local/Instaloader/session-<login>")

    def _create_filtering_tab(self, parent):
        self._add_option_widget(parent, "Fast Update (-F):", "--fast-update", widget_type="checkbutton")
        self._add_option_widget(parent, "Count (-c):", "--count", widget_type="spinbox", default_value="")
        self._add_option_widget(parent, "Latest Stamps File:", "--latest-stamps", browse_type="savefile", placeholder="Default: AppData/Local/Instaloader/latest-stamps.ini")
        self._add_option_widget(parent, "Post Filter (--only-if):", "--post-filter", col_span=2, placeholder="Python expression, e.g., viewer_has_liked")
        self._add_option_widget(parent, "StoryItem Filter:", "--storyitem-filter", col_span=2, placeholder="Python expression")

    def _create_path_options_tab(self, parent):
        self._add_option_widget(parent, "Dirname Pattern:", "--dirname-pattern", placeholder="Default: {target}", col_span=2)
        self._add_option_widget(parent, "Filename Pattern:", "--filename-pattern", placeholder="Default: {date_utc}_UTC", col_span=2)
        self._add_option_widget(parent, "Title Pattern:", "--title-pattern", placeholder="Default: varies", col_span=2)
        self._add_option_widget(parent, "Resume Prefix:", "--resume-prefix", placeholder="Internal use")
        self._add_option_widget(parent, "Sanitize Paths:", "--sanitize-paths", widget_type="checkbutton", default_value=True) # Often desired
        self._add_option_widget(parent, "NO Resume:", "--no-resume", widget_type="checkbutton")

    def _create_connection_misc_tab(self, parent):
        self._add_option_widget(parent, "User Agent:", "--user-agent", col_span=2)
        self._add_option_widget(parent, "Max Connection Attempts:", "--max-connection-attempts", default_value="3")
        self._add_option_widget(parent, "Request Timeout (sec):", "--request-timeout", default_value="300")
        self._add_option_widget(parent, "Abort on Status Codes:", "--abort-on", placeholder="e.g., 401,403")
        self._add_option_widget(parent, "NO iPhone Version:", "--no-iphone", widget_type="checkbutton")
        self._add_option_widget(parent, "Quiet (-q):", "--quiet", widget_type="checkbutton")


    def _update_command_preview(self, *args):
        parts = self._generate_command_list()
        try: preview = shlex.join(parts)
        except AttributeError: preview = " ".join(f'"{p}"' if " " in p else p for p in parts)
        self.command_preview_text.config(state='normal')
        self.command_preview_text.delete(1.0, tk.END)
        self.command_preview_text.insert(tk.END, preview)
        self.command_preview_text.config(state='disabled')

    def _update_command_preview_button_action(self):
        self._update_command_preview()

    def _generate_command_list(self):
        try: cmd = shlex.split(self.executable_var.get())
        except ValueError: cmd = []

        for key, var in self.option_vars.items():
            if isinstance(var, tk.BooleanVar):
                if var.get(): cmd.append(key)
            elif isinstance(var, (tk.StringVar, tk.IntVar)):
                val = str(var.get()).strip() 
                if key == "--password" and not val: continue 
                if val: 
                    is_default_placeholder = False
                    if key == "--max-connection-attempts" and val == "3": is_default_placeholder = True
                    if key == "--request-timeout" and val == "300": is_default_placeholder = True
                    if key == "--count" and val == "0": is_default_placeholder = True 

                    if not is_default_placeholder:
                        cmd.append(key)
                        cmd.append(val)
        
        # Handle targets
        target_type = self.target_type_var.get()
        if target_type != "profile": # A special target is selected
            cmd.append(target_type)
        else: # Use the text entry for targets
            targets_str = self.targets_var.get().strip()
            if targets_str:
                # Handle special cases like -- -shortcode
                processed_targets = []
                for t in targets_str.split():
                    if t.startswith("-") and not t.startswith("--"): # Likely a shortcode like -CqRstUvXwY_
                        processed_targets.extend(["--", t])
                    else:
                        processed_targets.append(t)
                cmd.extend(processed_targets)
        return cmd

    def _append_output(self, text):
        if self.winfo_exists():
            self.output_text.config(state='normal')
            self.output_text.insert(tk.END, text)
            self.output_text.see(tk.END)
            self.output_text.config(state='disabled')
            self.update_idletasks()

    def _run_instaloader_thread(self, command):
        try:
            self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            text=True, bufsize=1, universal_newlines=True,
                                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if self.winfo_exists():
                self.run_button.config(state=tk.DISABLED)
                self.stop_button.config(state=tk.NORMAL)

            if self.process.stdout:
                for line in iter(self.process.stdout.readline, ''):
                    if not line and self.process.poll() is not None: break
                    if line: self._append_output(line)
                self.process.stdout.close()
            
            stderr = ""
            if self.process.stderr:
                stderr = self.process.stderr.read()
                self.process.stderr.close()
            
            self.process.wait()
            if stderr: self._append_output(f"\n--- STDERR ---:\n{stderr}")
            self._append_output(f"\n--- Process finished with exit code {self.process.returncode} ---\n")
        except FileNotFoundError:
            self._append_output(f"Error: Command '{command[0] if command else ''}' not found.\nEnsure Instaloader is installed and in PATH or specify full command.\n")
        except Exception as e:
            self._append_output(f"An error occurred: {e}\n")
        finally:
            self.process = None
            if self.winfo_exists():
                self.run_button.config(state=tk.NORMAL)
                self.stop_button.config(state=tk.DISABLED)

    def _run_command(self):
        cmd_list = self._generate_command_list()
        # Check if any target is specified
        target_type = self.target_type_var.get()
        has_text_target = self.targets_var.get().strip()
        
        if target_type == "profile" and not has_text_target:
             # Check if the command list ALREADY contains a target (e.g. from +args.txt if we implement that later)
            has_explicit_target_in_cmd = any(t for t in cmd_list if not t.startswith('-') and t not in [self.executable_var.get()] + shlex.split(self.executable_var.get()) )

            if not has_explicit_target_in_cmd:
                messagebox.showerror("Error", "Please specify at least one target (profile, #hashtag, etc.) or select a special target type.")
                return

        if not cmd_list or not cmd_list[0]:
            messagebox.showerror("Error", "Instaloader command is not specified.")
            return

        self.output_text.config(state='normal'); self.output_text.delete(1.0, tk.END); self.output_text.config(state='disabled')
        self._append_output(f"Running: {shlex.join(cmd_list) if hasattr(shlex, 'join') else ' '.join(cmd_list)}\n\n")
        threading.Thread(target=self._run_instaloader_thread, args=(cmd_list,), daemon=True).start()

    def _stop_process(self):
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                try: self.process.wait(timeout=1)
                except subprocess.TimeoutExpired: self.process.kill()
                self._append_output("\n--- Process termination requested ---\n")
            except Exception as e: self._append_output(f"\nError stopping process: {e}\n")
            finally: self.process = None
        else: self._append_output("\n--- No active process or process already finished ---\n")
        if self.winfo_exists():
            self.run_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)

    def _clear_all_fields(self):
        self.targets_var.set("")
        self.target_type_var.set("profile") 

        for key, var in self.option_vars.items():
            if isinstance(var, tk.BooleanVar): var.set(False)
            elif isinstance(var, tk.StringVar):
                # Reset to known defaults or empty
                if key == "--max-connection-attempts": var.set("3")
                elif key == "--request-timeout": var.set("300")
                elif key == "--sanitize-paths": var.set(True) 
                else: var.set("")
            elif isinstance(var, tk.IntVar): 
                 if key == "--count": var.set(0) 
                 else: var.set(0)


        self._update_command_preview()
        messagebox.showinfo("Cleared", "All input fields reset.")

    def on_closing(self):
        if self.process and self.process.poll() is None:
            if messagebox.askyesno("Exit", "Instaloader process is running. Terminate and exit?"):
                self._stop_process()
                self.destroy()
            else: return
        self.destroy()

if __name__ == "__main__":
    app = InstaloaderGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()