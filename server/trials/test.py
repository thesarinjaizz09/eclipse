import pygame
import sys

pygame.init()

# Get display size (your monitor resolution)
info = pygame.display.Info()
screen_width, screen_height = info.current_w, info.current_h

# Load the background image
background = pygame.image.load("images/two_intersections.png")

# Scale background to fit screen
background = pygame.transform.scale(background, (screen_width, screen_height))

# Create window same size as scaled background
screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("Intersection Simulation")

# Convert for faster blitting
background = background.convert()

# Main loop
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Draw the background
    screen.blit(background, (0, 0))

    pygame.display.flip()

pygame.quit()
sys.exit()
