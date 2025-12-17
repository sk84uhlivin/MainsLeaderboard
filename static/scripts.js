let shinyOdds = 8192; // Default value
let game = 'crystal'; // Default game
let shinyGifsExists = true; // Assume true by default

document.addEventListener('DOMContentLoaded', function() {
    // Fetch config on load
    fetch('/config')
        .then(response => response.json())
        .then(cfg => {
            shinyOdds = cfg.shiny_odds || 8192;
            volume = cfg.volume || 0.5;
            game = cfg.game || 'crystal';
            shinyGifsExists = !!cfg.shiny_gifs_exists;
        })
        .catch(() => {
            // If config fetch fails, use defaults
        })
        .finally(() => {
            // Only call stat fetchers after config is loaded
            fetchTotalPokemon();
            fetchUniquePokemon();
            fetchAverageBst();
            fetchLowestBst();
            fetchLeaderboardData();
            fetchLast10Pokemon();
            fetchLocationPercentages();
            fetchCurrentStreak();
            fetchLongestStreak();
            fetchPokemonOptions();
            setDefaultDate();

            document.getElementById('entryForm').addEventListener('submit', function(event) {
                event.preventDefault();
                addEntry();
            });
        });
});

function escapeHtml(str) {
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function getMediaPath(pokemonName, shinyCheckCallback) {
    let shiny = 0;
    if (shinyGifsExists && Math.floor(Math.random() * shinyOdds) === 0) {
        if (typeof shinyCheckCallback === 'function') shinyCheckCallback();
        shiny = 1;
    }
    // Use the dynamic endpoint instead of static path
    return `/pokemon_media/${encodeURIComponent(pokemonName)}?shiny=${shiny}`;
}

let shinyMessageShown = false;
let volume = 0.5;
let shinyAudioClickListenerAdded = false; // Add this flag

function showShinyMessageAndAudio() {
    if (!shinyMessageShown) {
        fetch('/config')
			.then(response => response.json())
			.then(cfg => {
				volume = cfg.volume;
			})
			.catch(() => {
				// If config fetch fails, use default volume
			})
			.finally(() => {
				shinyMessageShown = true;
				const messageElem = document.getElementById('message');
				if (messageElem) {
					messageElem.textContent = '✨ A shiny Pokémon appeared! ✨';
				}
				const audio = new Audio('/static/shiny.mp3');
				audio.volume = volume;
				audio.play().catch(() => {
					if (messageElem) {
						messageElem.textContent += ' (Click anywhere to hear the shiny sound!)';
					}
					
					// Only add the click listener once
					if (!shinyAudioClickListenerAdded) {
						shinyAudioClickListenerAdded = true;
						const playShinyAudio = () => {
							const newAudio = new Audio('/static/shiny.mp3');
							newAudio.volume = volume;
							newAudio.play();
							document.removeEventListener('click', playShinyAudio);
							shinyAudioClickListenerAdded = false; // Reset flag when listener is removed
						};
						document.addEventListener('click', playShinyAudio);
					}
				});
            });
    }
}

function fetchTotalPokemon() {
    fetch('/total_pokemon')
        .then(response => response.json())
        .then(data => {
            const totalEntriesDiv = document.getElementById('totalEntries');
            totalEntriesDiv.textContent = `Total Pokemon: ${data.total_pokemon}`;
        })
        .catch(error => {
            console.error('Error fetching total Pokemon data:', error);
            document.getElementById('totalEntries').textContent = 'Total Pokemon: Error loading data.';
        });
}

function fetchUniquePokemon() {
    fetch('/unique_pokemon')
        .then(response => response.json())
        .then(data => {
            const uniqueEntriesDiv = document.getElementById('uniqueEntries');
            uniqueEntriesDiv.textContent = `Unique Pokemon: ${data.unique_pokemon}`;
        })
        .catch(error => {
            console.error('Error fetching unique Pokemon data:', error);
            document.getElementById('uniqueEntries').textContent = 'Unique Pokemon: Error loading data.';
        });
}

function fetchAverageBst() {
    fetch('/average_bst')
        .then(response => response.json())
        .then(data => {
            const averageBstDiv = document.getElementById('averageBst');
            averageBstDiv.textContent = `Average BST: ${data.average_bst}`;
        })
        .catch(error => {
            console.error('Error fetching average BST data:', error);
            document.getElementById('averageBst').textContent = 'Average BST: Error loading data.';
        });
}

function fetchLowestBst() {
    fetch('/lowest_bst')
        .then(response => response.json())
        .then(data => {
            const lowestBstDiv = document.getElementById('lowestBst');
            lowestBstDiv.textContent = `Lowest BST: ${data.lowest_bst}`;
        })
        .catch(error => {
            console.error('Error fetching lowest BST data:', error);
            document.getElementById('lowestBst').textContent = 'Lowest BST: Error loading data.';
        });
}

let showTimeSinceLast = false; // Start with Runs Since Last Ran
let showTimeSinceLastLeaderboard = false; // Separate toggle for leaderboard

function toggleSinceLastColumn() {
    showTimeSinceLast = !showTimeSinceLast;
    const header = document.getElementById('sinceLastHeader');
    header.innerHTML = `🔄 ${showTimeSinceLast ? 'Time Since Last Ran' : 'Runs Since Last Ran'}`;
    
    // Update only the column instead of refreshing the whole table
    updateLast10SinceLastColumn();
}

function updateLast10SinceLastColumn() {
    const last10Table = document.getElementById('last10Table').getElementsByTagName('tbody')[0];
    const rows = last10Table.getElementsByTagName('tr');
    
    fetch('/last10')
        .then(response => response.json())
        .then(data => {
            // Update only the 4th column (index 3) for each row
            for (let i = 0; i < rows.length && i < data.length; i++) {
                const entry = data[i];
                const sinceLastValue = showTimeSinceLast ? 
                    (entry["Time Since Last Ran"] || "") : 
                    (entry["Runs Since Last Ran"] || "");
                
                // Update only the last cell (column 3)
                rows[i].cells[3].textContent = sinceLastValue;
            }
        })
        .catch(error => {
            console.error('Error updating last 10 column:', error);
        });
}

function updateLeaderboardSinceLastColumn() {
    const leaderboardTable = document.getElementById('leaderboard').getElementsByTagName('tbody')[0];
    const rows = leaderboardTable.getElementsByTagName('tr');
    
    // We need to fetch the leaderboard data to get the current values
    fetch('/leaderboard')
        .then(response => response.json())
        .then(data => {
            // Create a lookup map: Pokemon name -> data
            const pokemonDataMap = {};
            data.forEach(row => {
                pokemonDataMap[row.Pokemon] = row;
            });
            
            // Update only the 6th column (index 5) for each row based on Pokemon name
            for (let i = 0; i < rows.length; i++) {
                // Get the Pokemon name from the current row (it's in the 2nd column, after the img tag)
                const pokemonCell = rows[i].cells[1];
                const pokemonName = pokemonCell.textContent.trim();
                
                // Find the corresponding data for this Pokemon
                const pokemonData = pokemonDataMap[pokemonName];
                if (pokemonData) {
                    const sinceLastValue = showTimeSinceLastLeaderboard ? 
                        (pokemonData["Time Since Last Ran"] || "") : 
                        (pokemonData["Runs Since Last Ran"] || "");
                    
                    // Update only the last cell (column 5)
                    rows[i].cells[5].textContent = sinceLastValue;
                }
            }
        })
        .catch(error => {
            console.error('Error updating leaderboard column:', error);
        });
}

function toggleLeaderboardSinceLastColumn() {
    showTimeSinceLastLeaderboard = !showTimeSinceLastLeaderboard;
    const header = document.getElementById('leaderboardSinceLastHeader');
    header.innerHTML = `🔄 ${showTimeSinceLastLeaderboard ? 'Time Since Last Ran' : 'Runs Since Last Ran'}`;
    
    // Update only the column instead of refreshing the whole table
    updateLeaderboardSinceLastColumn();
}

function fetchLeaderboardData() {
    fetch('/leaderboard')
        .then(response => response.json())
        .then(data => {
            const leaderboardTable = document.getElementById('leaderboard').getElementsByTagName('tbody')[0];
            leaderboardTable.innerHTML = '';

            data.forEach((row, index) => {
                const gifPath = getMediaPath(row.Pokemon, showShinyMessageAndAudio);

                // Choose which value to display based on current toggle state
                const sinceLastValue = showTimeSinceLastLeaderboard ? 
                    (row["Time Since Last Ran"] || "") : 
                    (row["Runs Since Last Ran"] || "");

                const newRow = leaderboardTable.insertRow();
                newRow.innerHTML = 
                    `<td>${index + 1}</td>
                    <td>
                        <img src="${gifPath}" alt="${row.Pokemon}" class="pokemon-gif">
                        <span class="pokemon-name-clickable" onclick="showPokemonEntries('${row.Pokemon.replace(/'/g, "\\'")}')">${row.Pokemon}</span>
                    </td>
                    <td>${row.BST}</td>
                    <td>${row.Count}</td>
                    <td>${row['Last Time Ran']}</td>
                    <td>${sinceLastValue}</td>`;
            });
        })
        .catch(error => {
            console.error('Error fetching leaderboard data:', error);
        });
}

function showPokemonEntries(pokemonName) {
    fetch(`/pokemon_entries/${encodeURIComponent(pokemonName)}`)
        .then(response => response.json())
        .then(data => {
            const modal = document.getElementById('pokemonModal');
            const modalPokemonName = document.getElementById('modalPokemonName');
            const modalPokemonGif = document.getElementById('modalPokemonGif');
            const modalLocationTableBody = document.getElementById('modalLocationTable').getElementsByTagName('tbody')[0];
            const modalEntriesTableBody = document.getElementById('modalEntriesTable').getElementsByTagName('tbody')[0];
            
            // Set the modal title
            modalPokemonName.textContent = `${pokemonName} - All Entries (${data.total_entries} total)`;
            
            // Set the Pokemon GIF
            const gifPath = getMediaPath(pokemonName, showShinyMessageAndAudio);
            modalPokemonGif.src = gifPath;
            modalPokemonGif.alt = pokemonName;
            
            // Clear existing content
            modalLocationTableBody.innerHTML = '';
            modalEntriesTableBody.innerHTML = '';
            
            // Populate location percentages table
            data.location_percentages.forEach(locationData => {
                const newRow = modalLocationTableBody.insertRow();
                const saniLocation = escapeHtml(locationData.location);
				newRow.innerHTML = `
                    <td>${saniLocation}</td>
                    <td>${locationData.count}</td>
                    <td>${locationData.percentage.toFixed(1)}%</td>
                `;
            });
            
            // Populate entries table
            data.entries.forEach(entry => {
                const newRow = modalEntriesTableBody.insertRow();
				const saniLocation = escapeHtml(entry.Location);
				const saniNotes = escapeHtml(entry.Notes || '');
                newRow.innerHTML = `
                    <td>${entry.Date}</td>
                    <td>${saniLocation}</td>
                    <td>${saniNotes}</td>
                `;
            });
            
            // Show the modal and prevent background scrolling
            modal.style.display = 'block';
            document.body.classList.add('modal-open');
        })
        .catch(error => {
            console.error('Error fetching Pokemon entries:', error);
        });
}

// Modal close functionality
document.addEventListener('DOMContentLoaded', function() {
    // ...existing code...
    
    // Add modal close handlers
    const modal = document.getElementById('pokemonModal');
    const closeBtn = document.querySelector('.close');
    
    // Function to close modal and restore background scrolling
    function closeModal() {
        modal.style.display = 'none';
        document.body.classList.remove('modal-open');
    }
    
    // Close modal when clicking the X
    closeBtn.onclick = closeModal;
    
    // Close modal when clicking outside of it
    window.onclick = function(event) {
        if (event.target === modal) {
            closeModal();
        }
    }
    
    // Close modal when pressing Escape key
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape' && modal.style.display === 'block') {
            closeModal();
        }
    });
    
    // Prevent scroll propagation from modal content
    const modalContent = document.querySelector('.modal-content');
    modalContent.addEventListener('wheel', function(event) {
        // Only prevent propagation if we're at the scroll limits
        const isAtTop = modalContent.scrollTop === 0;
        const isAtBottom = modalContent.scrollTop >= modalContent.scrollHeight - modalContent.clientHeight;
        
        if ((isAtTop && event.deltaY < 0) || (isAtBottom && event.deltaY > 0)) {
            event.preventDefault();
        }
    });
});

function fetchLast10Pokemon() {
    fetch('/last10')
        .then(response => response.json())
        .then(data => {
            const last10Table = document.getElementById('last10Table').getElementsByTagName('tbody')[0];
            last10Table.innerHTML = '';

            data.forEach(entry => {
                const gifPath = getMediaPath(entry.Pokemon, showShinyMessageAndAudio);
                
                // Choose which value to display based on current toggle state
                const sinceLastValue = showTimeSinceLast ? 
                    (entry["Time Since Last Ran"] || "") : 
                    (entry["Runs Since Last Ran"] || "");

                const newRow = last10Table.insertRow();
				const saniLocation = escapeHtml(entry.Location);
                newRow.innerHTML = 
                    `<td>
                        <img src="${gifPath}" alt="${entry.Pokemon}" class="pokemon-gif">
                        ${entry.Pokemon}
                    </td>
                    <td>${entry.Date}</td>
                    <td>${saniLocation}</td>
                    <td>${sinceLastValue}</td>`;
            });
        })
        .catch(error => {
            console.error('Error fetching last 10 Pokemon data:', error);
        });
}

function fetchLocationPercentages() {
    fetch('/location_percentages')
        .then(response => response.json())
        .then(data => {
            const locationPercentagesTable = document.getElementById('locationPercentages').getElementsByTagName('tbody')[0];
            locationPercentagesTable.innerHTML = '';

            data.forEach(entry => {
                const newRow = locationPercentagesTable.insertRow();
				const saniLocation = escapeHtml(entry.Location);
				const saniPokemon = escapeHtml(entry.LastPokemon);
				const saniDate = escapeHtml(entry.LastDate);
                newRow.innerHTML = 
                    `<td>${saniLocation}</td>
                    <td>${entry.Percentage.toFixed(2)}%</td>
                    <td>${saniPokemon} (${saniDate})</td>`;
            });
        })
        .catch(error => {
            console.error('Error fetching location percentages data:', error);
        });
}

function fetchCurrentStreak() {
    fetch('/current_streak')
        .then(response => response.json())
        .then(data => {
            const streakDiv = document.getElementById('currentStreak');
            streakDiv.textContent = `Current Streak: ${data.current_streak} day${data.current_streak === 1 ? '' : 's'}`;
        })
        .catch(error => {
            console.error('Error fetching current streak:', error);
            document.getElementById('currentStreak').textContent = 'Current Streak: Error loading data.';
        });
}

function fetchLongestStreak() {
    fetch('/longest_streak')
        .then(response => response.json())
        .then(data => {
            const longestStreakDiv = document.getElementById('longestStreak');
            let streakText = `Longest Streak: ${data.longest_streak} day${data.longest_streak === 1 ? '' : 's'}`;
            if (data.start_date && data.end_date) {
                streakText += ` (${data.start_date} - ${data.end_date})`;
            }
            longestStreakDiv.textContent = streakText;
        })
        .catch(error => {
            console.error('Error fetching longest streak:', error);
            document.getElementById('longestStreak').textContent = 'Longest Streak: Error loading data.';
        });
}

function fetchPokemonOptions() {
	fetch('/bst')
		.then(response => response.json())
        .then(data => {
            const pokemonOptions = document.getElementById('pokemon_dataset');

            data.forEach(entry => {
                const newOption = document.createElement('option');
                newOption.value = entry.Pokemon;
				pokemonOptions.appendChild(newOption);
            });
        })
        .catch(error => {
            console.error('Error fetching Pokemon Options:', error);
        });
}


function setDefaultDate() {
	const today = new Date();
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, '0'); // Months are 0-based
    const dd = String(today.getDate()).padStart(2, '0');
    document.getElementById('date').defaultValue = `${yyyy}-${mm}-${dd}`;
}

async function addEntry() {
    const form = document.getElementById('entryForm');
    const formData = new FormData(form);
    
    // Trim whitespace from form fields before sending
    const pokemon = formData.get('pokemon').trim();
    const location = formData.get('location').trim();
    const notes = formData.get('notes').trim();
    
    // Check if required fields are empty after trimming
    if (!pokemon || !location) {
        document.getElementById('message').textContent = 'Pokemon and Location are required.';
        return;
    }
    
    // Create new FormData with trimmed values
    const trimmedFormData = new FormData();
    trimmedFormData.append('pokemon', pokemon);
    trimmedFormData.append('location', location);
    trimmedFormData.append('date', formData.get('date'));
    trimmedFormData.append('notes', notes);

	const bst_response = await fetch('/bst');
	const bst_json = await bst_response.json();
	const validPokemon = bst_json.find(item => item.Pokemon === pokemon);
	
	if (validPokemon) {
		fetch('/add_entry', {
			method: 'POST',
			body: trimmedFormData
		})
		.then(response => response.json())
		.then(data => {
			if (data.success) {
				fetchTotalPokemon(); // Update the total Pokemon count
				fetchUniquePokemon();
				fetchAverageBst(); // Update the average BST
				fetchLowestBst();
				fetchLeaderboardData();
				fetchLast10Pokemon();
				fetchLocationPercentages();
				fetchCurrentStreak(); // <-- Updated line
				fetchLongestStreak(); // <-- Added line
				document.getElementById('entryForm').reset();
				document.getElementById('message').textContent = 'Entry added successfully.';
			} else {
				document.getElementById('message').textContent = 'Failed to add entry.';
			}
		})
		.catch(error => {
			console.error('Error adding new entry:', error);
			document.getElementById('message').textContent = 'Error adding new entry.';
		});
	} else {
		console.error('Invalid Pokemon Entered');
		document.getElementById('message').textContent = 'Invalid Pokemon Entered';
	}
	
}

let sortOrder = [true, false, false, false, false]; // Track sort order for each column (added one more for new column)

function sortTable(columnIndex) {
    // Prevent sorting on the toggle column (index 5)
    if (columnIndex === 5) {
        return;
    }
    
    const table = document.getElementById('leaderboard');
    const tbody = table.getElementsByTagName('tbody')[0];
    const rows = Array.from(tbody.getElementsByTagName('tr'));

    // Store original order for tiebreaking
    rows.forEach((row, index) => {
        row.setAttribute('data-original-order', index);
    });

    // Determine the sort direction
    sortOrder[columnIndex] = !sortOrder[columnIndex];

    // Clear existing arrows
    const arrows = ['rankArrow', 'pokemonArrow', 'bstArrow', 'countArrow', 'lastTimeRanArrow'];
    arrows.forEach((id, index) => {
        const arrow = document.getElementById(id);
        arrow.classList.remove('up', 'down');
        arrow.style.visibility = 'hidden'; // Hide all arrows
    });

    // Sort rows based on the specified column index
    rows.sort((a, b) => {
        const aText = a.cells[columnIndex].textContent.trim();
        const bText = b.cells[columnIndex].textContent.trim();

        let comparison = 0;

        // Handle different column types
        if (columnIndex === 0) { // Rank (numeric sort)
            comparison = parseInt(aText) - parseInt(bText);
        } else if (columnIndex === 2 || columnIndex === 3) { // BST, Count (numeric sort)
            comparison = parseInt(aText) - parseInt(bText);
        } else if (columnIndex === 4) { // Last Time Ran (date sort)
            const aDate = new Date(aText);
            const bDate = new Date(bText);
            comparison = aDate - bDate;
            
            // If dates are equal, use original order as tiebreaker (most recent CSV entry first)
            if (comparison === 0) {
                const aOriginalOrder = parseInt(a.getAttribute('data-original-order'));
                const bOriginalOrder = parseInt(b.getAttribute('data-original-order'));
                comparison = aOriginalOrder - bOriginalOrder;
            }
        } else { // Alphabetical sort for Pokemon name
            comparison = aText.localeCompare(bText);
        }

        // Apply sort direction
        return sortOrder[columnIndex] ? comparison : -comparison;
    });

    // Update the arrow for the sorted column (only for columns that have arrows)
    if (columnIndex < arrows.length) {
        const arrow = document.getElementById(arrows[columnIndex]);
        arrow.style.visibility = 'visible'; // Show the arrow
        arrow.classList.add(sortOrder[columnIndex] ? 'up' : 'down');
    }

    // Remove existing rows and append sorted rows
    tbody.innerHTML = '';
    rows.forEach(row => {
        row.removeAttribute('data-original-order'); // Clean up
        tbody.appendChild(row);
    });
}

function fetchMaxRunsPerDay() {
    fetch('/max_runs_per_day')
        .then(response => response.json())
        .then(data => {
            const maxRunsDiv = document.getElementById('maxRunsPerDay');
            if (data.max_runs && data.dates && data.dates.length > 0) {
                maxRunsDiv.textContent = `Most Runs in a Day: ${data.max_runs} (${data.dates.join(', ')})`;
            } else {
                maxRunsDiv.textContent = 'Most Runs in a Day: N/A';
            }
        })
        .catch(error => {
            console.error('Error fetching max runs per day:', error);
            document.getElementById('maxRunsPerDay').textContent = 'Most Runs in a Day: Error loading data.';
        });
}

// In DOMContentLoaded, add:
fetchMaxRunsPerDay();

