import tkinter as tk
from tkinter import simpledialog, messagebox, filedialog
from PIL import Image, ImageTk, ImageDraw  # Requires: pip install pillow

# Default settings
CELL_SIZE = 40

# Fallback colors if no tileset is loaded
COLORS = {
    0: "white", 1: "#00ccff", 2: "#00ff00", 3: "#ff9900", 4: "#ff0000",
    5: "#9900ff", 6: "#ff00ff", 7: "#ffff00", 8: "#999999", 9: "#006600",
    10: "#000000"
}

class GridPainter:
    def __init__(self, root, rows=8, cols=14):
        self.root = root
        self.rows = rows
        self.cols = cols
        self.cell_size = CELL_SIZE
        self.current_id = 1 # Default ID (1 is usually the first solid tile)
        self.grid = [[0 for _ in range(cols)] for _ in range(rows)]
        
        # Image storage
        self.tile_images = [] # List of ImageTk.PhotoImage objects
        self.tileset_loaded = False

        # --- Main Layout ---
        # We use a PanedWindow to separate Grid (left) and Palette (right)
        self.paned_window = tk.PanedWindow(root, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        # --- LEFT: Editor Frame ---
        self.editor_frame = tk.Frame(self.paned_window)
        self.paned_window.add(self.editor_frame, minsize=400)

        # Scrollable Canvas for Grid
        self.grid_canvas = tk.Canvas(self.editor_frame, bg="white")
        self.hbar = tk.Scrollbar(self.editor_frame, orient=tk.HORIZONTAL, command=self.grid_canvas.xview)
        self.vbar = tk.Scrollbar(self.editor_frame, orient=tk.VERTICAL, command=self.grid_canvas.yview)
        self.grid_canvas.configure(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)

        self.hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.grid_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.grid_canvas.bind("<Button-1>", self.paint_cell)
        self.grid_canvas.bind("<B1-Motion>", self.paint_cell)
        # Add Right-click to erase (set to 0)
        self.grid_canvas.bind("<Button-3>", self.erase_cell)
        self.grid_canvas.bind("<B3-Motion>", self.erase_cell)

        # --- RIGHT: Palette/Controls Frame ---
        self.controls_frame = tk.Frame(self.paned_window, width=200, bg="#f0f0f0")
        self.paned_window.add(self.controls_frame, minsize=180)

        # Controls Buttons
        tk.Label(self.controls_frame, text="Controls", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=5)
        
        tk.Button(self.controls_frame, text="Load Tileset Image", command=self.load_tileset, bg="#dddddd").pack(fill=tk.X, padx=5, pady=2)
        tk.Button(self.controls_frame, text="Resize Grid", command=self.resize_grid_dialog, bg="#dddddd").pack(fill=tk.X, padx=5, pady=2)
        tk.Button(self.controls_frame, text="Copy Export", command=self.export_to_clipboard, bg="#dddddd").pack(fill=tk.X, padx=5, pady=2)
        
        self.lbl_current = tk.Label(self.controls_frame, text=f"Selected ID: {self.current_id}", bg="#f0f0f0")
        self.lbl_current.pack(pady=10)

        # Palette Label
        tk.Label(self.controls_frame, text="Palette", font=("Arial", 10, "bold"), bg="#f0f0f0").pack(pady=5)

        # --- Palette Scroll Frame ---
        self.palette_frame = tk.Frame(self.controls_frame, bg="#e0e0e0")
        self.palette_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Scrollbar for Palette
        self.palette_scrollbar = tk.Scrollbar(self.palette_frame, orient=tk.VERTICAL)
        self.palette_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Palette Canvas
        self.palette_canvas = tk.Canvas(self.palette_frame, bg="#e0e0e0", yscrollcommand=self.palette_scrollbar.set)
        self.palette_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Link scrollbar
        self.palette_scrollbar.config(command=self.palette_canvas.yview)

        self.palette_canvas.bind("<Button-1>", self.select_tile_from_palette)
        
        # Bind Mousewheel logic (only when hovering over palette)
        self.palette_canvas.bind("<Enter>", self._bind_mousewheel)
        self.palette_canvas.bind("<Leave>", self._unbind_mousewheel)

        # To store grid object references
        self.rects = [[None for _ in range(self.cols)] for _ in range(self.rows)]
        
        # Initial Draw
        self.draw_grid()

    # --- Mousewheel Handlers ---
    def _bind_mousewheel(self, event):
        self.palette_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.palette_canvas.bind_all("<Button-4>", self._on_mousewheel) # Linux scroll up
        self.palette_canvas.bind_all("<Button-5>", self._on_mousewheel) # Linux scroll down

    def _unbind_mousewheel(self, event):
        self.palette_canvas.unbind_all("<MouseWheel>")
        self.palette_canvas.unbind_all("<Button-4>")
        self.palette_canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        if event.num == 5 or event.delta < 0:
            self.palette_canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            self.palette_canvas.yview_scroll(-1, "units")

    # --- Tileset Logic ---
    def load_tileset(self):
        file_path = filedialog.askopenfilename(
            title="Select Tileset Image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif")]
        )
        if not file_path:
            return

        try:
            # 1. Load Image
            pil_image = Image.open(file_path)
            
            # 2. Ask for Layout
            t_rows = simpledialog.askinteger("Tileset Info", "How many ROWS in this tileset?", minvalue=1, initialvalue=1)
            t_cols = simpledialog.askinteger("Tileset Info", "How many COLUMNS in this tileset?", minvalue=1, initialvalue=1)
            
            if not t_rows or not t_cols:
                return

            # 3. Slice Image
            img_w, img_h = pil_image.size
            tile_w = img_w / t_cols
            tile_h = img_h / t_rows

            self.tile_images = [] # Clear old tiles

            # --- INSERT AIR TILE AT INDEX 0 ---
            # Create a placeholder image for "Air" (Index 0)
            air_img = Image.new('RGB', (self.cell_size, self.cell_size), color='#ffffff')
            draw = ImageDraw.Draw(air_img)
            # Draw a red X to represent empty/air
            draw.line((0, 0, self.cell_size, self.cell_size), fill="#ffcccc", width=2)
            draw.line((0, self.cell_size, self.cell_size, 0), fill="#ffcccc", width=2)
            draw.rectangle((0, 0, self.cell_size-1, self.cell_size-1), outline="#cccccc")
            
            self.tile_images.append(ImageTk.PhotoImage(air_img))
            # ----------------------------------

            for r in range(t_rows):
                for c in range(t_cols):
                    # Crop the individual tile
                    left = c * tile_w
                    top = r * tile_h
                    right = left + tile_w
                    bottom = top + tile_h
                    
                    crop = pil_image.crop((left, top, right, bottom))
                    # Resize to fit our editor cell size
                    crop = crop.resize((self.cell_size, self.cell_size), Image.NEAREST)
                    
                    photo = ImageTk.PhotoImage(crop)
                    self.tile_images.append(photo)

            self.tileset_loaded = True
            self.current_id = 1 # Reset selection to first REAL tile (since 0 is air)
            self.draw_palette()
            self.draw_grid() # Redraw grid with new images
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load tileset:\n{e}")

    def draw_palette(self):
        """Draws the loaded tiles into the right-hand sidebar."""
        self.palette_canvas.delete("all")
        
        pad = 5
        col_count = 3 # How many columns in the palette view
        
        current_y = pad
        current_x = pad
        
        for i, img in enumerate(self.tile_images):
            # Draw the image
            self.palette_canvas.create_image(current_x, current_y, image=img, anchor=tk.NW, tags=f"tile_{i}")
            
            # Label index 0 as "Air"
            if i == 0:
                 self.palette_canvas.create_text(current_x + self.cell_size/2, current_y + self.cell_size/2, text="AIR", fill="red", font=("Arial", 8))

            # Highlight if selected
            if i == self.current_id:
                self.palette_canvas.create_rectangle(
                    current_x, current_y, 
                    current_x + self.cell_size, current_y + self.cell_size, 
                    outline="red", width=3
                )

            # Move position
            current_x += self.cell_size + pad
            
            # Wrap to next row
            if (i + 1) % col_count == 0:
                current_x = pad
                current_y += self.cell_size + pad

        # Update scroll region of palette to fit all items
        # Add extra padding at the bottom so the last item isn't cut off
        self.palette_canvas.config(scrollregion=(0, 0, 200, current_y + self.cell_size + 20))

    def select_tile_from_palette(self, event):
        if not self.tileset_loaded:
            return
        
        pad = 5
        col_count = 3
        
        # Calculate index based on x/y click
        # IMPORTANT: Use canvasy to account for scrolling offset!
        canvas_y = self.palette_canvas.canvasy(event.y)
        
        col = (event.x - pad) // (self.cell_size + pad)
        row = (canvas_y - pad) // (self.cell_size + pad)
        
        index = int(row * col_count + col)
        
        if 0 <= index < len(self.tile_images):
            self.current_id = index
            tile_name = "Air/Empty" if index == 0 else f"Tile {index}"
            self.lbl_current.config(text=f"Selected ID: {self.current_id} ({tile_name})")
            self.draw_palette() # Redraw to update red outline highlight

    # --- Grid Functions ---
    def draw_grid(self):
        self.grid_canvas.delete("all")
        self.rects = [[None for _ in range(self.cols)] for _ in range(self.rows)]
        
        width = self.cols * self.cell_size
        height = self.rows * self.cell_size
        self.grid_canvas.config(scrollregion=(0, 0, width, height))
        
        for r in range(self.rows):
            for c in range(self.cols):
                self.draw_single_cell(r, c)

    def draw_single_cell(self, r, c):
        """Helper to draw a single cell based on current state"""
        x1 = c * self.cell_size
        y1 = r * self.cell_size
        
        val = self.grid[r][c]

        # If there is an existing item, remove it
        if self.rects[r][c]:
            self.grid_canvas.delete(self.rects[r][c])

        if self.tileset_loaded and 0 <= val < len(self.tile_images):
            # Draw Image (This now handles ID 0 because we added an image for it)
            self.rects[r][c] = self.grid_canvas.create_image(
                x1, y1, image=self.tile_images[val], anchor=tk.NW
            )
        else:
            # Draw Color (Fallback)
            color = COLORS.get(val, "white")
            self.rects[r][c] = self.grid_canvas.create_rectangle(
                x1, y1, x1 + self.cell_size, y1 + self.cell_size, 
                fill=color, outline="gray"
            )

    def paint_cell(self, event):
        # Adjust for scrolling
        x = self.grid_canvas.canvasx(event.x)
        y = self.grid_canvas.canvasy(event.y)
        
        c = int(x // self.cell_size)
        r = int(y // self.cell_size)
        
        if 0 <= r < self.rows and 0 <= c < self.cols:
            if self.grid[r][c] != self.current_id:
                self.grid[r][c] = self.current_id
                self.draw_single_cell(r, c)

    def erase_cell(self, event):
        """Shortcut to paint 0 (Air) with right click"""
        x = self.grid_canvas.canvasx(event.x)
        y = self.grid_canvas.canvasy(event.y)
        
        c = int(x // self.cell_size)
        r = int(y // self.cell_size)
        
        if 0 <= r < self.rows and 0 <= c < self.cols:
            if self.grid[r][c] != 0:
                self.grid[r][c] = 0
                self.draw_single_cell(r, c)

    # --- Resizing ---
    def resize_grid_dialog(self):
        new_rows = simpledialog.askinteger("Resize", "Number of rows:", minvalue=1, maxvalue=1000)
        new_cols = simpledialog.askinteger("Resize", "Number of columns:", minvalue=1, maxvalue=1000)
        if new_rows and new_cols:
            self.resize_grid(new_rows, new_cols)

    def resize_grid(self, new_rows, new_cols):
        new_grid = [[0 for _ in range(new_cols)] for _ in range(new_rows)]
        # Preserve overlapping cells
        for r in range(min(self.rows, new_rows)):
            for c in range(min(self.cols, new_cols)):
                new_grid[r][c] = self.grid[r][c]
        self.rows, self.cols, self.grid = new_rows, new_cols, new_grid
        self.draw_grid()

    # --- Export ---
    def export_to_clipboard(self):
        # Start the C-style array structure
        text = "{\n"
        
        for row in self.grid:
            # Convert all integers in the row to strings
            # UPDATED: No longer adding +1. 0 is Air, 1 is first texture.
            row_values = [str(v) for v in row]
            
            # Join them with commas
            line = ", ".join(row_values)
            
            # Add indentation and a trailing comma (because it is one long 1D array)
            text += f"    {line},\n"
            
        # Close the structure
        text += "};"

        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        messagebox.showinfo("Copied!", "Map Array copied to clipboard.\n(0 = Air, 1+ = Texture IDs)")

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Grid Painter with Tilesets")
    root.geometry("1000x600")
    app = GridPainter(root)
    root.mainloop()
