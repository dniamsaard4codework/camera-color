    frame = cv2.flip(frame, 1)
            self.current_frame = frame
            height, width = frame.shape[:2]
            
            # Analyze top and bottom halves
            top_half = frame[:height//2, :]
            bottom_half = frame[height//2:, :]
            
            self.current_colors[0] = tuple(np.mean(top_half, axis=(0, 1)).astype(int))
            self.current_colors[1] = tuple(np.mean(bottom_half, axis=(0, 1)).astype(int))
            
            time.sleep(0.03)  # ~30 fps