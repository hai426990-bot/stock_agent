import akshare as ak
import pandas as pd

def check_sectors():
    print("Checking Industry Sectors...")
    try:
        ind_df = ak.stock_board_industry_name_em()
        print(f"Found {len(ind_df)} industry sectors")
        baijiu_ind = ind_df[ind_df['板块名称'].str.contains('白酒')]
        if not baijiu_ind.empty:
            print("Industry matches for '白酒':")
            print(baijiu_ind)
        else:
            print("No industry matches for '白酒'")
    except Exception as e:
        print(f"Error fetching industry sectors: {e}")

    print("\nChecking Concept Sectors...")
    try:
        con_df = ak.stock_board_concept_name_em()
        print(f"Found {len(con_df)} concept sectors")
        baijiu_con = con_df[con_df['板块名称'].str.contains('白酒')]
        if not baijiu_con.empty:
            print("Concept matches for '白酒':")
            print(baijiu_con)
        else:
            print("No concept matches for '白酒'")
    except Exception as e:
        print(f"Error fetching concept sectors: {e}")

if __name__ == "__main__":
    check_sectors()
