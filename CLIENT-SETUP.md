# Armando Furniture - Demo Setup Guide

## First time setup

1. Install **Docker Desktop** (free): https://www.docker.com/products/docker-desktop
   - After installing, open Docker Desktop once and wait until it says
     "Docker Desktop is running."
2. Extract the demo folder anywhere on your computer.
3. Double-click **start-demo.bat**.
4. Wait for your browser to open automatically to the application.
   - The very first time, this can take a few minutes while everything
     downloads and sets up.
5. **Create your first account.** No user account is set up for you
   automatically - on the login page, click **Create Account** (or
   **Register**) and fill in a username and password. Once you've
   created an account, log in with it normally from then on.

## Daily use

- **Start**: double-click `start-demo.bat`
- **Stop**: double-click `stop-demo.bat`

Your data (products, resources, transactions, history, etc.) is kept
between starts and stops - you do not lose anything by stopping the
application.

## Important notes

- **Do not delete the Docker volume** (shown in Docker Desktop / `docker
  volume ls` as `armando-furniture-client_armando_client_postgres_data`).
  This is where all your data is stored. Deleting it deletes your data.
- **Password reset is console-based for this demo.** There is no email
  set up yet, so if someone uses "Forgot Password," the reset link
  will not be emailed - it is printed to the application's log instead
  of being sent. Ask whoever set up the demo to check the log
  (`docker compose -f docker-compose.client.yml logs backend`) for the
  link if this happens.
- The application runs at **http://localhost:3000** in your web
  browser. Keep the Docker Desktop application running in the
  background while you use it.

## If you need to start completely fresh

There is a `reset-demo.bat` script available, but **it permanently
deletes all data** (products, resources, transactions, everything) and
cannot be undone. Only use it if you are sure you want to erase
everything and start over - it will ask you to type YES to confirm
before doing anything.

## Something not working?

- Make sure Docker Desktop is open and running (you should see its
  icon in the system tray).
- Try double-clicking `stop-demo.bat` and then `start-demo.bat` again.
- To see what the application is doing behind the scenes, you (or
  whoever is helping you) can run:
  `docker compose -f docker-compose.client.yml logs`
