import streamlit as st
import pygame
import numpy as np

# Set the page configuration for a wider layout
st.set_page_config(layout="wide")

# Initialize Pygame in headless mode (no visible window)
pygame.init()
pygame.display.init()

# Define screen dimensions
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

# Create a Pygame surface to draw on
screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

# Pygame simulation variables
car_x = 0
car_y = 300
car_speed = 5
clock = pygame.time.Clock()

def run_simulation(start_sim):
    """
    This function contains the main Pygame loop and is called by Streamlit.
    """
    global car_x
    
    # Placeholder for the Streamlit image element.
    # We will update this element on each frame.
    frame_placeholder = st.empty()
    
    # The main simulation loop
    if start_sim:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return

            # --- Simulation Logic ---
            
            # Clear the screen (background)
            screen.fill((255, 255, 255)) # White background

            # Move the car
            car_x += car_speed
            if car_x > SCREEN_WIDTH:
                car_x = 0

            # Draw the road
            pygame.draw.rect(screen, (100, 100, 100), (0, SCREEN_HEIGHT / 2 - 25, SCREEN_WIDTH, 50))
            
            # Draw the car (a simple rectangle for this example)
            pygame.draw.rect(screen, (255, 0, 0), (car_x, car_y, 50, 30))

            # --- Display Frame in Streamlit ---
            
            # Get the pixel data from the Pygame surface
            # This is a key step to convert Pygame output to a format Streamlit can use.
            frame_data = pygame.surfarray.array3d(screen)
            
            # Update the placeholder with the new frame.
            frame_placeholder.image(frame_data, channels="RGB", use_column_width=True)

            # Limit the frame rate
            clock.tick(60)

# --- Streamlit Dashboard Layout ---

st.title("Pygame Traffic Simulation Dashboard")

st.markdown("""
This is a live, embedded Pygame simulation running directly within a Streamlit dashboard. 
You can control the simulation using the controls below.
""")

# Add a button to start and stop the simulation
if st.button("Start Simulation"):
    run_simulation(True)

# You can add more dashboard controls here
st.sidebar.header("Simulation Controls")
car_speed = st.sidebar.slider(
    "Car Speed",
    min_value=1,
    max_value=20,
    value=5,
    help="Adjust the speed of the red car."
)

st.sidebar.markdown("---")
st.sidebar.info("The simulation will run at a fixed FPS for smooth playback.")

# Call the simulation function on initial load
if not "simulation_started" in st.session_state:
    st.session_state.simulation_started = True
    run_simulation(False)
