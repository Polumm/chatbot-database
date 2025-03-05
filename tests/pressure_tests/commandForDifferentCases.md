# 🚀 Command Lines for Different Test Scenarios

Below are different command-line executions for various test cases. Run these in your terminal to test different load conditions.

---

## **Common Commands**
First enter the folder:

```sh
cd tests/pressure_tests
```

Generate mock users:
```sh
python create_mock_users.py
```

Clean up after tests by:
```sh
python rollback_test_data.py
redis-cli clushall # clean up whole redis keys
```

## **Test Scenario Overview**

| Scenario                          | Users | Spawn Rate | Duration | Expected Outcome |
|------------------------------------|-------|------------|----------|------------------|
| **High Load Test (Heavy Traffic)** | 500   | 50/sec     | 10m      | Check Redis/PostgreSQL under stress |
| **Real User Simulation (Slow Load)** | 10   | 1/sec      | 10m      | Test real-world behavior |
| **Redis Failure Test (No Cache)**  | 100   | 10/sec     | 5m       | Ensure PostgreSQL fallback works |
| **Spam Attack (Message Flooding)** | 50    | 10/sec     | 5m       | Detect rate-limiting issues |
| **Large Data Retrieval (Slow Query Test)** | 20 | 5/sec | 5m | Measure Redis query performance |
| **Traffic Spike (Short Burst Load)** | 100  | 100/sec    | 1m       | Test API’s ability to handle bursts |
| **Stability Test (Long-Running Load)** | 50  | 5/sec     | 1h       | Detect slowdowns/memory leaks |
| **Testing on a Staging Server**    | 20    | 5/sec      | 10m      | Check performance on staging environment |

---

## **1️⃣ High Load Test (Heavy Traffic)**
✔ Simulates **500 users** spawning at **50/sec** for **10 minutes**.

```sh
python run_locust.py --users 500 --spawn-rate 50 --run-time 10m
```

---

## **2️⃣ Real User Simulation (Slow Load)**
✔ Simulates **10 users** with a slow **1/sec spawn rate** for **10 minutes**.

```sh
python run_locust.py --users 10 --spawn-rate 1 --run-time 10m
```

---

## **3️⃣ Redis Failure Test (No Cache)**
✔ Tests **100 users** while Redis is **manually stopped**.

```sh
sudo systemctl stop redis  # Stop Redis first
python run_locust.py --users 100 --spawn-rate 10 --run-time 5m
```

---

## **4️⃣ Spam Attack (Message Flooding)**
✔ Simulates bot-like behavior with **50 users** sending messages aggressively.

```sh
python run_locust.py --users 50 --spawn-rate 10 --run-time 5m
```

---

## **5️⃣ Large Data Retrieval (Slow Query Test)**
✔ Fetches messages from large chat histories to test performance.

```sh
python run_locust.py --users 20 --spawn-rate 5 --run-time 5m
```

---

## **6️⃣ Traffic Spike (Short Burst Load)**
✔ Tests how the system handles a **sudden surge** of users.

```sh
python run_locust.py --users 100 --spawn-rate 100 --run-time 1m
```

---

## **7️⃣ Stability Test (Long-Running Load)**
✔ Runs for **1 hour** to check for **memory leaks** and **performance degradation**.

```sh
python run_locust.py --users 50 --spawn-rate 5 --run-time 1h
```

---

## **8️⃣ Testing on a Staging Server**
✔ Targets a **different environment** instead of `localhost`.

```sh
python run_locust.py --host http://staging.example.com --users 20 --spawn-rate 5 --run-time 10m
```

---

## **🛠️ Customizing Further**
📌 **Adjust `--users`, `--spawn-rate`, and `--run-time`** as needed.  
📌 **Use `--headless` for automated CI/CD testing.**  
📌 **Monitor logs to analyze API behavior under stress.**

