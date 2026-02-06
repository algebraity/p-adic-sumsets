import subprocess

def ads_algorithm(n, p):
        result = subprocess.run(
            ["./ads_p", f"{p}", f"{n}"],
            capture_output=True,
            text=True,
            check=True
        )
        # Parse the final line: "n, |A|, |A+A|"
        output_lines = result.stdout.strip().split('\n')
        for line in output_lines:
            if line.startswith(str(n) + ","):
                parts = line.split(",")
                A_size = int(parts[1].strip())
                AA_size = int(parts[2].strip())
        return A_size, AA_size

def main(n, p, i):
    for n in range(1+i, 201, i):
        A1, AA1 = ads_algorithm(n, p)

        s = set([i * (p**j) for i in range(1, n+1) for j in range(1, n+1)])
        ads = set([x + y for x in s for y in s])
        A2 = len(s)
        AA2 = len(ads)

        if A1 == A2 and AA1 == AA2:
            print(f"All good for {n} :3    |    {A1}, {AA1}")
        elif A1 != A2:
            print(f"WARNING!!!! A1 != A2 for {n} >:(")
        elif AA1 != AA2:
            print(f"WARNING!!!! AA1 != AA2 for {n} >:(")

if __name__ == "__main__":
    p = int(input("Enter p: "))
    n = int(input("Enter n: "))
    i = int(input("Enter i: "))
    main(n, p, i) 
