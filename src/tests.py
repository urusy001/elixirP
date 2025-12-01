def baking_contest(time_left, pastries):
    if time_left == 0 or pastries == []:
        return 0

    elif isinstance(pastries, list) and isinstance(pastries[0], list):
        if time_left < pastries[0][1] or len(pastries) > 1 and pastries[1][2] / pastries[1][1] > pastries[0][2] / pastries[0][1] and pastries[1][1] <= time_left:
            return baking_contest(time_left, pastries[1:])

        else:
            return baking_contest(time_left, pastries[0]) + baking_contest(time_left-pastries[0][1], pastries[1:])

    else:
        return pastries[2]



if __name__ == '__main__':
    print()
    #Should output 50 (real way) or 100 (easy way)
    #Gujiya + Taiyaki
    print(baking_contest(92, [['Gujiya', 55, 30],
                              ['Taiyaki', 35, 20],
                              ['Conejito', 60, 40],
                              ['Apple Strudel', 40, 10]]))
    #Should output 40 (real way) or 100 (easy way)
    #Conejito
    print(baking_contest(76, [['Gujiya', 55, 30],
                              ['Taiyaki', 35, 20],
                              ['Conejito', 60, 40],
                              ['Apple Strudel', 40, 10]]))

    #Should output 88 (real way) or 142 (easy way)
    #Beaver Tail + Makmur + Pionono + Sfenj
    print(baking_contest(147, [['Alfajores', 30, 14],
                               ['Banket', 25, 16],
                               ['Beaver Tail', 50, 30],
                               ['Fa Gao', 55, 24],
                               ['Makmur', 45, 25],
                               ['Pionono', 22, 15],
                               ['Sfenj', 30, 18]]))

    #Should output 142 (real way) or 142 (easy way)
    #Enough time to get every pastry
    print(baking_contest(300, [['Alfajores', 30, 14],
                               ['Banket', 25, 16],
                               ['Beaver Tail', 50, 30],
                               ['Fa Gao', 55, 24],
                               ['Makmur', 45, 25],
                               ['Pionono', 22, 15],
                               ['Sfenj', 30, 18]]))
    #Should output 0 (real way) or 142 (easy way)
    #Not enough time for any pastries
    print(baking_contest(21, [['Alfajores', 30, 14],
                              ['Banket', 25, 16],
                              ['Beaver Tail', 50, 30],
                              ['Fa Gao', 55, 24],
                              ['Makmur', 45, 25],
                              ['Pionono', 22, 15],
                              ['Sfenj', 30, 18]]))
