from PIL import Image, ImageDraw
import os

def combine_images(image_a_path, image_b_path, image_c_path, output_path, target_size=(200, 200), padding=50):
    # Open and resize images
    img_a = Image.open(image_a_path).convert('RGBA')
    img_b = Image.open(image_b_path).convert('RGBA')
    img_c = Image.open(image_c_path).convert('RGBA')

    # Calculate maximum dimensions that would fit in target_size while maintaining aspect ratio
    def scale_to_fit(img, max_size):
        ratio = min(max_size[0]/img.width, max_size[1]/img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        return img.resize(new_size, Image.Resampling.LANCZOS)

    # Scale images if they're too large
    img_a = scale_to_fit(img_a, target_size)
    img_b = scale_to_fit(img_b, target_size)
    img_c = scale_to_fit(img_c, target_size)

    # Calculate total height of A+B including gap
    left_side_height = img_a.height + 20 + img_b.height

    # Calculate minimum width needed for the layout
    min_width = img_a.width + 100 + img_c.width + (padding * 2)
    min_height = max(left_side_height, img_c.height) + (padding * 2)

    # Create a white background image
    combined = Image.new('RGBA', (min_width, min_height), 'white')

    # Calculate vertical center
    vertical_center = min_height // 2

    # Calculate positions (with padding)
    a_pos = (padding, padding + (min_height - 2*padding - left_side_height) // 2)  # Center A+B vertically
    b_pos = (padding, a_pos[1] + img_a.height + 20)  # Position B below A
    c_pos = (padding + img_a.width + 100, vertical_center - img_c.height // 2)  # Center C vertically

    # Paste images
    combined.paste(img_a, a_pos, img_a)
    combined.paste(img_b, b_pos, img_b)
    combined.paste(img_c, c_pos, img_c)

    # Draw arrow
    draw = ImageDraw.Draw(combined)
    
    # Light orange color (RGB)
    arrow_color = '#FFA500'  # Orange color
    outline_color = 'black'  # Black outline
    
    # Calculate arrow points for horizontal arrow at vertical center
    arrow_start_x = padding + img_a.width + 10
    arrow_start_y = vertical_center  # Center arrow vertically
    arrow_end_x = c_pos[0] - 10
    arrow_end_y = arrow_start_y

    # Arrow body parameters
    arrow_width = 12  # Reduced width of arrow body
    arrow_head_size = 25  # Size of arrow head

    # Calculate points for arrow body (rectangle)
    top_left = (arrow_start_x, arrow_start_y - arrow_width/2)
    top_right = (arrow_end_x - arrow_head_size, arrow_start_y - arrow_width/2)
    bottom_right = (arrow_end_x - arrow_head_size, arrow_start_y + arrow_width/2)
    bottom_left = (arrow_start_x, arrow_start_y + arrow_width/2)

    # Draw arrow body with outline
    draw.polygon([top_left, top_right, bottom_right, bottom_left], 
                fill=arrow_color, 
                outline=outline_color)

    # Calculate arrow head points for horizontal arrow
    left_point = (arrow_end_x - arrow_head_size, arrow_end_y - arrow_head_size/2)
    right_point = (arrow_end_x - arrow_head_size, arrow_end_y + arrow_head_size/2)
    
    # Draw arrow head with outline
    draw.polygon([
        (arrow_end_x, arrow_end_y),
        left_point,
        right_point
    ], fill=arrow_color, outline=outline_color)

    # Save the combined image
    combined.save(output_path, 'PNG')

def process_image_folders(folder_a, folder_b, image_c, output_folder, target_size=(500,500), padding=50):
    # Create output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)
    
    # Get the list of files in folder A
    files_a = sorted([f for f in os.listdir(folder_a) if f.endswith('.png')])
    files_b = sorted([f for f in os.listdir(folder_b) if f.endswith('.png')])
    
    
    # Process each pair of images
    for i in range(len(files_a)):
        image_a = os.path.join(folder_a, files_a[i])
        image_b = os.path.join(folder_b, files_b[i])
        output_path = os.path.join(output_folder, f"{files_a[i]}")
        
        print(f"Processing {files_a[i]}... {output_path}")
        
        try:
            combine_images(
                image_a,
                image_c,
                image_b,
                output_path,
                target_size=target_size,
                padding=padding
            )
        except Exception as e:
            print(f"Error processing {files_a[i]}: {str(e)}")

if __name__ == "__main__":
    # Configure these paths
    folder_a = "/home/will/work/ai/roop/temp copy/f50fd2da-1ecc-4f1e-99d3-9e5c1b287dc5"
    folder_b = "/home/will/work/ai/roop/temp copy/exampleori"
    image_c = "/home/will/work/ai/roop/temp copy/cheng.png"
    output_folder = "/home/will/work/ai/roop/temp copy/output"
    
    process_image_folders(
        folder_a,
        folder_b,
        image_c,
        output_folder,
        target_size=(150,150),
        padding=12
    )
