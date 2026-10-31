<h1>r/ultrahardcore Statistics Dashboard</h1>

<h2>Introduction</h2>
<p>
            This dashboard was developed by <strong><t style="color: #807fd1;"> plumjuice </t></strong>
            as an alternative visualization tool for various stats and other information
            of the r/ultrahardcore community's recorded rounds (RRs), players, 
            and RR gamemodes as extracted from <strong><a href="https://docs.google.com/spreadsheets/d/1cJnD5KPdTL1g_8CkWGiaibcpg00WKa2KgsGHzQnKnc8/edit?usp=sharing",
            style="text-decoration: none; color: #3962dd;">
            @ripperstevem5's Global RR Stats Community Document</a></strong>, 
            with the main goals of convenience and scalability in mind.
            In addition to being a stat viewer, this dashboard also includes some experimental
            potentially useful tools such as a player skill rating system, team builder, and UHC simulator.</p>
            
<h2>Existing Version</h2>
The current version available in the repository is updated to 1/18/2026.  Given the following known issues, until further notice, it is not advised to use the "Update" feature in the dashboard settings.

<h2>Current Known Issues for Updating to August 2026</h2>
<ul>
            <li><strong>Alternate Usernames Detection and therefore Updates are Broken:</strong> UPDATE AT YOUR OWN RISK!!! Updating results in split player statistics for each new username.  A fix is currently being worked on (highest priority).</li>
            <li><strong>Yearly Statistics Leaderboard will not show:</strong> The database-to-display pipeline is currently being revamped.</li>
            <li><strong>Updating Aggregate Statistics</strong> may result in some issues with players who have recently changed their usernames.</li>
            <li><strong>Updating during Spreadsheet Update: </strong>It is uncertain whether or not updating the database during a spreadsheet update will result in broken entries.</li>       
            <li><strong>Absence of Collaboration Season Detection: </strong> At the moment, there is no means of automatically and reliably detecting duplicate rounds under different names, and waiting for a manual update of the database is recommended until further notice.</li>
            <li><strong>Cinema Rating Distribution Error: </strong> Cinema's round profile does not properly generate rating distributions past season 12</li>
</ul>

<h2>Feature Overview</h2>
<ul>
            <li>Leaderboard</li>
            <li>Round Profiles</li>
            <li>Player Profiles</li>
            <li>Round Simulator</li>
            <li>Settings and Update</li>
</ul>

<h2>Leaderboard</h2>
The leaderboard section consists of three different sub-tabs: the main leaderboard, the special statistics leaderboard, and the scatter view, accessible through selecting an option from the drop-down menu at the top right.

<h3>Main Leaderboard</h3>
The main leaderboard displays all players that have played at least the threshold number (Minimum Games Threshold) of rounds, adjustable at the top of the page.  Changing the settings at the top of the page (Sort By, Lifetime/Year Modes, Minimum Games Threshold) will automatically reupdate the leaderboard.  Checking the box "Show Redacted" will show banned/excommunicated/redacted players.

<h3>Extra Statistics Leaderboard</h3>
The extra leaderboard displays metrics that could not be displayed within the main leaderboard:  Deadliest Players (by count/%), Longest Ironman (time without taking damage), and Latest First Damage (time until first damage is taken).

<h3>Scatter View</h3>
The scatter view consists of two dropdowns for the X and Y axis variables and displays all metrics from players who meet the Minimum Games Threshold criterion.  Hovering over the scatter points will show the username, X value, and Y value of the referent player.

<h2>Round Profiles</h2>

<h3>Searching</h3>
Round Profiles are separated into two sections: active and inactive rounds.  Typing into the search bar will filter the rounds by the input string (case-insensitive).  Profile pages for each round can be accessed by clicking on the desired round name.

<h3>Round Profile</h3>
Round Profiles consist of various trivia and stats, visualizations for roster size and rating distribution (subject to change throughout the year), and links to individual season pages.

<h3>Season Pages</h3>
In each season page are information and killfeeds as found in the Community Stats Spreadsheet, with the addition of rankings of kill leaders by count and percentage of the roster size, as well as rankings of deadliest teams.


<h2>Player Profiles</h2>

<h3>Searching</h3>
Similar to Round Profiles, Player Profiles will show filtered results based on the input string (case-insensitive).  Redacted players will still appear in the results list.  Player profiles can be accessed by clicking on a player's name.  To search for another user while on a profile, simply reuse the search bar to find another user.

<h3>Player Page</h3>
Each player has their own profile page that consist of the following:
<ul><h3>Left Column</h3>
            <li><strong>IGN</strong> - As recorded in the Global RR Stats Community Document</li>
            <li><strong>Current Skin</strong> - Fetched from Mineatar API with IGN (If the skin is not showing, Mojang API or Mineatar API may be down, or the player currently uses a different name than what is recorded in the document)</li>
            <li><strong>Debut RR</strong> - The earliest recorded round played </li>
            <li><strong>Most Recent RR</strong> - The most recently released round played</li>
            <li><strong>Rounds Played</strong> - Total number of rounds played </li>
            <li><strong>Rating</strong> (experimental, WIP) - A graph shows the distribution of ratings for a given year (adjustable for relevant years using the dropdown), and a vertical line indicates the player's position within the distribution.  A dotted line (rather than a solid line), indicates that the player has played less than 5 rounds in the chosen year.  A metric calculated on a per-year basis to approximate a player's relative performance to other players, and is given by the following equation: (a "?" beside the rating and percentile indicates less than 5 rounds played that year)<br>
                        <ul>$$R_{t} = 100 \cdot (0.5 \cdot P_t + 0.25 \cdot KPR_t + 0.25 \cdot C_t)$$
            <br><br>
                        <li>$$R_t =\textbf{Performance rating for } t \textbf{ year}$$<br></li>
                        <li>$$P_t = \textbf{PageRank score for } t \textbf{ year}$$<br></li>
                        <li>$$KPR_t = \textbf{Average kills per round for } t \textbf{ year}$$<br></li>
                        <li>$$C_t = \textbf{Consistency score for } t \textbf{ year}$$</li>
                                    <br>
                                    <ul>$$C_t = \frac{\mu_t}{1 + \sigma_t}$$<br>
                                                <li>$$\mu_t = \textbf{Average head to head record against all players for } t \textbf{ year}$$</li>
                                                <li>$$\sigma_t = \textbf{Standard Deviation of head to head records against all players for } t \textbf{ year}$$</li>
                                    </ul>
                                    </ul></li>
</ul>
<ul><h3>Kill Stats</h3>
            <li><strong>Lifetime Kills</strong>: Total kills up to the latest update</li>
            <li><strong>Q(1-4) | H(1-2) | (Year) Kills</strong>: Current Quarterly, Semiannual, Yearly Kill Counts</li>
            <li><strong>Lifetime KDR</strong>: Aggregate Kill to Death Ratio</li>
            <li><strong>Q(1-4) | H(1-2) | (Year) KDR</strong>: Aggregate Kill to Death Ratio by Quarter, Half, Year</li>
            <li><strong>Lifetime KPR</strong>: Aggregate Kill to Rounds Played Ratio</li>
            <li><strong>Q(1-4) | H(1-2) | (Year) KPR</strong>: Aggregate Kill to Rounds Played Ratio by Quarter, Half, Year</li>
            <li><strong>First Bloods</strong>: Number of rounds in which this player eliminated another player first (% of rounds played)</li>
            <li><strong>Top Frags</strong>: Number of rounds in which this player eliminated the most other players (% of rounds played)</li>
            <li><strong>Killl Record</strong>: The most eliminations a player has achieved in a single round.</li>
</ul>
<ul><h3>Death Stats</h3>
            <li>
</ul>

<h2>Round Simulator</h2>
<h2>Settings and Update</h2>
